import abc
import importlib
import inspect
import logging
import pathlib
import sys
import typing
import uuid

import langchain_core.tools
import pydantic
import sentence_transformers
import yaml

from .types import (
    ToolKind,
    SQLPPQueryMetadata,
    SemanticSearchMetadata,
    HTTPRequestMetadata
)

# TODO: Should core.tool depend upon core.catalog, or the other
# way? Ideally, it's not a cross-dependency both ways?
from ..catalog.descriptor import ToolDescriptor


# TODO: Need unified logging approach across rosetta?
# TODO: Since this is a library, can a custom logger
# implementation be passed in by the app?
logger = logging.getLogger(__name__)


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
        front_matter = yaml.safe_load(SQLPPQueryMetadata.read_front_matter(filename))
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
