import abc
import importlib
import inspect
import logging
import pathlib
import sys
import typing

import langchain_core.tools
import pydantic
import yaml

from .types import (
    ToolKind,
    SQLPPQueryMetadata,
    SemanticSearchMetadata,
    HTTPRequestMetadata
)

# TODO: Should core.tool depend upon core.catalog, or the other
# way? Ideally, it's not a cross-dependency both ways?
from .types.descriptor import ToolDescriptor


# TODO: Need unified logging approach across rosetta?
# TODO: Since this is a library, can a custom logger
# implementation be passed in by the app?
logger = logging.getLogger(__name__)


# TODO: Need to support index scanning, but not doing any
# real work, such as to support "rosetta status", such as
# to detect when local catalog is out of date -- or such
# as when running with a "rosetta index --dry-run" option?

# TODO: We should use something other than ValueError,
# such as by capturing line numbers, etc?


class BaseFileIndexer(pydantic.BaseModel):
    @abc.abstractmethod
    def start_descriptors(self, filename: pathlib.Path, get_repo_commit_id) -> \
        typing.Tuple[list[ValueError], list[ToolDescriptor]]:
        """Returns zero or more 'bare' catalog item descriptors for a filename,
           and/or return non-fatal or 'keep-on-going' errors if any encountered.

           The returned descriptors are 'bare' in that they only capture
           immediately available information and properties. Any slow
           operators such as LLM augmentation, vector embeddings, etc. are
           handled by other methods & processing phases that are called later.

           A 'keep-on-going' error means the top level command should
           ultimately error, but more processing on other files might
           still be attempted to increase the user's productivity --
           e.g., show the user multiple error messages instead of
           giving up on the very first encountered error.
        """
        pass


class DotPyFileIndexer(BaseFileIndexer):
    def start_descriptors(self, filename: pathlib.Path, get_repo_commit_id) -> \
        typing.Tuple[list[ValueError], list[ToolDescriptor]]:
        """Returns zero or more 'bare' catalog item descriptors
           for a *.py, and/or returns 'keep-on-going' errors
           if any encountered.
        """

        # TODO (GLENN): We should avoid blindly putting things in our path.
        if str(filename.parent.absolute()) not in sys.path:
            sys.path.append(str(filename.parent.absolute()))

        # TODO: See if we can avoid relying on langchain_core or othern
        # agent framework? Potentially with a duck-typing approach instead?
        is_tool = lambda n, t: isinstance(t, langchain_core.tools.BaseTool)

        i = importlib.import_module(filename.stem)

        descriptors = []

        repo_commit_id = None # Ex: a git hash / SHA.

        for name, tool in inspect.getmembers(i):
            if not is_tool(name, tool):
                continue

            name = tool.name.strip()

            if not repo_commit_id:
                repo_commit_id = get_repo_commit_id(filename)

            descriptors.append(ToolDescriptor(
                identifier=str(filename) + ":" + name + ":" + repo_commit_id,
                kind=ToolKind.PythonFunction,
                name=name,
                description=tool.description.strip(),
                # TODO: Capture line numbers as part of source?
                source=filename,
                repo_commit_id=repo_commit_id,
                deleted=False,
                # TODO: The embedding is filled in at a later phase.
                embedding=[],
            ))

        return (None, descriptors)


class DotSqlppFileIndexer(BaseFileIndexer):
    def start_descriptors(self, filename: pathlib.Path, get_repo_commit_id) -> \
        typing.Tuple[list[ValueError], list[ToolDescriptor]]:
        """Returns zero or 1 'bare' catalog item descriptors
           for a *.sqlpp, and/or return 'keep-on-going' errors
           if any encountered.
        """

        front_matter = SQLPPQueryMetadata.read_front_matter(filename)

        metadata = SQLPPQueryMetadata.model_validate(front_matter)

        name = metadata.name.strip() # TODO: If missing, name should default to filename?

        repo_commit_id = get_repo_commit_id(filename) # Ex: a git hash / SHA.

        return (None, [ToolDescriptor(
            identifier=str(filename) + ":" + name + ":" + repo_commit_id,
            kind=ToolKind.SQLPPQuery,
            name=name,
            description=metadata.description.strip(),
            source=filename,
            repo_commit_id=repo_commit_id,
            deleted=False,
            # TODO: The embedding is filled in at a later phase.
            embedding=[],
        )])


class DotYamlFileIndexer(BaseFileIndexer):
    def start_descriptors(self, filename: pathlib.Path, get_repo_commit_id) -> \
        typing.Tuple[list[ValueError], list[ToolDescriptor]]:
        """Returns zero or more 'bare' catalog item descriptors
           for a *.yaml, and/or return 'keep-on-going' errors
           if any encountered.
        """

        with filename.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)

        if 'tool_kind' not in parsed_desc:
            logger.warning(f'Encountered .yaml file with unknown tool_kind field. '
                            f'Not indexing {str(filename.absolute())}.')
            return (None, [])

        repo_commit_id = get_repo_commit_id(filename) # Ex: a git hash / SHA.

        match parsed_desc['tool_kind']:
            case ToolKind.SemanticSearch:
                metadata = SemanticSearchMetadata.model_validate(parsed_desc)

                name = metadata.name.strip() # TODO: If missing, name should default to filename?

                return (None, [ToolDescriptor(
                    identifier=str(filename) + ":" + name + ":" + repo_commit_id,
                    kind=ToolKind.SemanticSearch,
                    name=name,
                    description=metadata.description.strip(),
                    source=filename,
                    repo_commit_id=repo_commit_id,
                    deleted=False,
                    # TODO: The embedding is filled in at a later phase.
                    embedding=[],
                )])

            case ToolKind.HTTPRequest:
                metadata = HTTPRequestMetadata.model_validate(parsed_desc)

                descriptors = []

                for operation in metadata.open_api.operations:
                    name = operation.specification.operation_id.strip()

                    descriptors.append(ToolDescriptor(
                        identifier=str(filename) + ":" + name + ":" + repo_commit_id,
                        kind=ToolKind.HTTPRequest,
                        name=name,
                        description=operation.specification.description.strip(),
                        # TODO: Capture line numbers as part of source?
                        source=filename,
                        repo_commit_id=repo_commit_id,
                        deleted=False,
                        # TODO: The embedding is filled in at a later phase.
                        embedding=[],
                    ))

                return (None, descriptors)

            case _:
                logger.warning(f'Encountered .yaml file with unknown tool_kind field. '
                                f'Not indexing {str(filename.absolute())}.')

        return (None, [])


source_indexers = {
    '*.py': DotPyFileIndexer(),
    '*.sqlpp': DotSqlppFileIndexer(),
    '*.yaml': DotYamlFileIndexer()
}


def augment_descriptor(descriptor: ToolDescriptor) -> list[ValueError]:
    """ Augments a single catalog item descriptor (in-place, destructive),
        with additional information, such as generated by an LLM,
        and/or return 'keep-on-going' errors if any encountered.
    """

    # TODO: Different source file types might have
    # different ways of augmenting a descriptor?

    return None


def vectorize_descriptor(descriptor: ToolDescriptor, embedding_model_obj) -> \
    list[ValueError]:
    """ Adds vector embeddings to a single catalog item descriptor (in-place,
        destructive), and/or return 'keep-on-going' errors if any encountered.
    """

    # TODO: Different source file types might have different ways
    # to compute & add vector embedding(s), perhaps by using additional
    # fields besides description?

    descriptor.embedding = embedding_model_obj.encode(descriptor.description).tolist()

    return None