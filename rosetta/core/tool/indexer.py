import abc
import importlib
import inspect
import logging
import pathlib
import sys
import typing
import uuid

import pydantic
import langchain_core.tools
import sentence_transformers
import yaml

from .types import (
    ToolKind,
    SQLPPQueryMetadata,
    SemanticSearchMetadata,
    HTTPRequestMetadata
)
from .common import get_front_matter_from_dot_sqlpp

# TODO: Should core.tool depend upon core.catalog, or the other
# way? Ideally, it's not a cross-dependency both ways?
from ..catalog.descriptor import ToolDescriptor


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
    def start_descriptors(self, filename: pathlib.Path, rev_ident_fn) -> \
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

    def augment_descriptor(self, descriptor: ToolDescriptor) -> \
        list[ValueError]:
        """Augments a single catalog item descriptor (in-place, destructive),
           with additional information, such as generated by an LLM,
           and/or return 'keep-on-going' errors if any encountered.
        """

        # TODO: Not sure whether different source file types
        # will actually have different ways to augment a descriptor?

        return None

    def vectorize_descriptor(self, descriptor: ToolDescriptor, embedding_model) -> \
        list[ValueError]:
        """Adds vector embeddings to a single catalog item descriptor,
           and/or return 'keep-on-going' errors if any encountered.
        """

        # TODO: Not sure whether different source file types
        # will actually have different ways to compute & add
        # vector embedding(s), perhaps by using additional
        # fields besides description?

        descriptor.embedding = embedding_model.encode(descriptor.description).tolist()

        return None


class DotPyFileIndexer(BaseFileIndexer):
    def start_descriptors(self, filename: pathlib.Path, rev_ident_fn) -> \
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

        rev_ident = None # A revision identifier. Ex: a git hash / SHA.

        for name, tool in inspect.getmembers(i):
            if not is_tool(name, tool):
                continue

            if not rev_ident:
                rev_ident = rev_ident_fn(filename)

            descriptors.append(ToolDescriptor(
                identifier=str(filename) + ":" + tool.name + ":" + rev_ident,
                name=tool.name,
                description=tool.description,
                # TODO: Capture line numbers as part of source?
                source=str(filename),
                kind=ToolKind.PythonFunction,
            ))

        return (None, descriptors)


class DotSqlppFileIndexer(BaseFileIndexer):
    def start_descriptors(self, filename: pathlib.Path, rev_ident_fn) -> \
        typing.Tuple[list[ValueError], list[ToolDescriptor]]:
        """Returns zero or 1 'bare' catalog item descriptors
           for a *.sqlpp, and/or return 'keep-on-going' errors
           if any encountered.
        """

        front_matter = yaml.safe_load(get_front_matter_from_dot_sqlpp(filename))

        metadata = SQLPPQueryMetadata.model_validate(front_matter)

        rev_ident = rev_ident_fn(filename)

        return (None, ToolDescriptor(
            identifier=str(filename) + ":" + metadata.name + ":" + rev_ident,
            name=metadata.name, # TODO: Should default to filename?
            description=metadata.description,
            source=str(filename),
            kind=ToolKind.SQLPPQuery,
        ))


class DotYamlFileIndexer(BaseFileIndexer):
    def start_descriptors(self, filename: pathlib.Path, rev_ident_fn) -> \
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

        match parsed_desc['tool_kind']:
            case ToolKind.SemanticSearch:
                metadata = SemanticSearchMetadata.model_validate(parsed_desc)
                return (None, ToolDescriptor(
                    identifier=str(filename) + ":" + metadata.name + ":" + rev_ident_fn(filename),
                    name=metadata.name, # TODO: Should default to filename?
                    description=metadata.description,
                    source=str(filename),
                    kind=ToolKind.SemanticSearch
                ))
            case ToolKind.HTTPRequest:
                metadata = HTTPRequestMetadata.model_validate(parsed_desc)

                descriptors = []

                rev_ident = rev_ident_fn(filename) # A revision identifier. Ex: a git hash / SHA.

                for operation in metadata.open_api.operations:
                    descriptors.append(ToolDescriptor(
                        identifier=str(filename) + ":" + operation.specification.operation_id + ":" + rev_ident,
                        name=operation.specification.operation_id,
                        description=operation.specification.description,
                        # TODO: Capture line numbers as part of source?
                        source=str(filename),
                        kind=ToolKind.HTTPRequest
                    ))
            case _:
                logger.warning(f'Encountered .yaml file with unknown tool_kind field. '
                                f'Not indexing {str(filename.absolute())}.')


source_indexers = {
    '*.py': DotPyFileIndexer(),
    '*.sqlpp': DotSqlppFileIndexer(),
    '*.yaml': DotYamlFileIndexer()
}

# ------------------------------------------

# TODO: Old code that's undergoing refactoring...

# TODO: Does Indexer need to be a pydantic model -- is it saved/stored somewhere?
class Indexer(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    embedding_model: sentence_transformers.SentenceTransformer = pydantic.Field(
        description="Embedding model used to encode the tool descriptions."
    )

    @abc.abstractmethod
    def index(self, module_locations: list[pathlib.Path]):
        pass

    @staticmethod
    def _generate_tool_id(*args, **kwargs) -> str:
        # TODO (GLENN): Use a better ID here.
        return uuid.uuid4().hex

    def _encode_description(self, description: str):
        # TODO (GLENN): Handle large descriptions in embedding model.
        return self.embedding_model.encode(description).tolist()

    def _handle_dot_py(self, filename: pathlib.Path) -> typing.Iterable[ToolDescriptor]:
        is_tool = lambda n, t: isinstance(t, langchain_core.tools.BaseTool)

        # TODO (GLENN): We should avoid blindly putting things in our path.
        if str(filename.parent.absolute()) not in sys.path:
            sys.path.append(str(filename.parent.absolute()))

        i = importlib.import_module(filename.stem)
        for name, tool in inspect.getmembers(i):
            if not is_tool(name, tool):
                continue

            # Yield our descriptor.
            yield ToolDescriptor(
                identifier=self._generate_tool_id(),
                name=tool.name,
                description=tool.description,
                embedding=self._encode_description(tool.description),
                source=str(filename.absolute()),
                kind=ToolKind.PythonFunction,
            )

    def _handle_dot_sqlpp(self, filename: pathlib.Path) -> typing.Iterable[ToolDescriptor]:
        front_matter = yaml.safe_load(get_front_matter_from_dot_sqlpp(filename))
        metadata = SQLPPQueryMetadata.model_validate(front_matter)

        # Build our tool descriptor.
        yield ToolDescriptor(
            identifier=self._generate_tool_id(),
            name=metadata.name,
            description=metadata.description,
            embedding=self._encode_description(metadata.description),
            source=str(filename.absolute()),
            kind=ToolKind.SQLPPQuery,
        )

    def _handle_dot_yaml(self, filename: pathlib.Path) -> typing.Iterable[ToolDescriptor]:
        with filename.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)
        if 'tool_kind' not in parsed_desc:
            logger.warning(f'Encountered .yaml file with unknown tool_kind field. '
                           f'Not indexing {str(filename.absolute())}.')
            return

        match parsed_desc['tool_kind']:
            case ToolKind.SemanticSearch:
                metadata = SemanticSearchMetadata.model_validate(parsed_desc)
                yield ToolDescriptor(
                    identifier=self._generate_tool_id(),
                    name=metadata.name,
                    description=metadata.description,
                    embedding=self._encode_description(metadata.description),
                    source=str(filename.absolute()),
                    kind=ToolKind.SemanticSearch
                )
            case ToolKind.HTTPRequest:
                metadata = HTTPRequestMetadata.model_validate(parsed_desc)
                for operation in metadata.open_api.operations:
                    yield ToolDescriptor(
                        identifier=self._generate_tool_id(),
                        name=operation.specification.operation_id,
                        description=operation.specification.description,
                        embedding=self._encode_description(operation.specification.description),
                        source=str(filename.absolute()),
                        kind=ToolKind.HTTPRequest
                    )
            case _:
                logger.warning(f'Encountered .yaml file with unknown tool_kind field. '
                               f'Not indexing {str(filename.absolute())}.')


class LocalIndexer(Indexer):
    catalog_file: pathlib.Path

    def index(self, module_locations: list[pathlib.Path]):
        tool_catalog_entries = list()
        for directory in module_locations:
            for member in directory.iterdir():
                match member.suffix:
                    case '.py':
                        member_handler = self._handle_dot_py
                    case '.yaml':
                        member_handler = self._handle_dot_yaml
                    case '.sqlpp':
                        member_handler = self._handle_dot_sqlpp
                    case _:
                        logger.debug(f'Not indexing {str(member.absolute())}.')
                        continue
                for descriptor in member_handler(member):
                    tool_catalog_entries.append(descriptor)

        with self.catalog_file.open('w') as fp:
            for entry in tool_catalog_entries:
                fp.write(entry.model_dump_json() + '\n')
