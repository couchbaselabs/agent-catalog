import json
import pydantic
import sentence_transformers
import langchain_core.tools
import logging
import abc
import pathlib
import sys
import typing
import uuid
import importlib
import yaml
import inspect

from .helper import (
    get_front_matter_from_dot_sqlpp
)
from .descriptor import (
    ToolDescriptor,
    ToolKind
)

logger = logging.getLogger(__name__)


class Registrar(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    embedding_model: sentence_transformers.SentenceTransformer = pydantic.Field(
        description="Embedding model used to encode the tool descriptions."
    )

    @abc.abstractmethod
    def index(self, module_locations: typing.List[pathlib.Path]):
        pass

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
                identifier=uuid.uuid4(),
                name=tool.name,
                description=tool.description,
                embedding=self._encode_description(tool.description),
                source=str(filename.absolute()),
                kind=ToolKind.PythonFunction,
            )

    def _handle_dot_sqlpp(self, filename: pathlib.Path) -> typing.Iterable[ToolDescriptor]:
        front_matter = yaml.safe_load(get_front_matter_from_dot_sqlpp(filename))

        # TODO (GLENN): Handle large descriptions in embedding model.
        # Build our tool descriptor.
        description = front_matter['Description'].strip()
        yield ToolDescriptor(
            identifier=uuid.uuid4(),
            name=front_matter['Name'],
            description=description,
            embedding=self._encode_description(description),
            source=str(filename.absolute()),
            kind=ToolKind.SQLPPQuery,
        )

    def _handle_dot_yaml(self, filename: pathlib.Path) -> typing.Iterable[ToolDescriptor]:
        with filename.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)
        match parsed_desc['Tool Class']:
            case ToolKind.SemanticSearch:
                yield from self._handle_semantic_search(filename, parsed_desc)
            case ToolKind.HTTPRequest:
                yield from self._handle_http_request(filename, parsed_desc)
            case _:
                logger.warning(f'Encountered .yaml file with unknown Tool Class. '
                               f'Not indexing {str(filename.absolute())}.')

    def _handle_semantic_search(self, filename: pathlib.Path, desc: typing.Dict) -> typing.Iterable[ToolDescriptor]:
        description = desc['Description'].strip()
        yield ToolDescriptor(
            identifier=uuid.uuid4(),
            name=desc['Name'],
            description=desc['Description'].strip(),
            embedding=self._encode_description(description),
            source=str(filename.absolute()),
            kind=ToolKind.SemanticSearch
        )

    def _handle_http_request(self, filename: pathlib.Path, desc: typing.Dict) -> typing.Iterable[ToolDescriptor]:
        if 'Open API' not in desc:
            logger.warning(f'HTTP Request tool must be specified using an Open API spec. '
                           f'Not indexing {str(filename.absolute())}.')
            return []

        # Read our specification file. All we want to do is find the descriptions for each endpoint.
        spec_file = pathlib.Path(desc['Open API']['File'])
        if not spec_file.exists():
            logger.error('Could not locate the Open API spec file.')
            raise FileNotFoundError()
        with spec_file.open('r') as fp:
            parsed_spec = json.load(fp)

        if 'Endpoints' not in desc['Open API']:
            error_message = f'Bad Open API specification given! Using file: {str(filename.absolute())}'
            logger.error(error_message)
            raise KeyError(error_message)
        for endpoint in desc['Open API']['Endpoints']:
            operation, path_item = endpoint.split(' ', 1)
            if path_item not in parsed_spec['paths']:
                logger.warning(f'{path_item} not found in Open API specification. Skipping.')
                continue

            # We need a description to continue.
            item_in_spec = parsed_spec['paths'][path_item][operation.lower()]
            if 'description' not in item_in_spec:
                logger.warning(f'No description found for Open API endpoint {endpoint}. Skipping.')
                continue
            tool_description = item_in_spec['description']
            yield ToolDescriptor(
                identifier=uuid.uuid4(),
                name=item_in_spec['operationId'],
                description=tool_description,
                embedding=self._encode_description(tool_description),
                source=str(filename.absolute()),
                kind=ToolKind.HTTPRequest,
            )


class LocalRegistrar(Registrar):
    catalog_file: pathlib.Path

    def index(self, module_locations: typing.List[pathlib.Path]):
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


class CouchbaseRegistrar(Registrar):
    pass
