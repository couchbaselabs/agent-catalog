import pydantic
import sentence_transformers
import langchain_core.tools
import logging
import abc
import os
import pathlib
import sys
import typing
import uuid
import importlib
import yaml
import inspect

from .tooling import (
    ToolDescriptor,
    ToolKind
)

logger = logging.getLogger(__name__)


class Registrar(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    embedding_model: sentence_transformers.SentenceTransformer = pydantic.Field(
        default_factory=lambda: sentence_transformers.SentenceTransformer(os.getenv('DEFAULT_SENTENCE_EMODEL')),
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
        if not str(filename.parent.absolute()) in sys.path:
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
                encoding=self._encode_description(tool.description),
                source=str(filename.absolute()),
                kind=ToolKind.PythonFunction,
            )

    def _handle_dot_sqlpp(self, filename: pathlib.Path) -> ToolDescriptor:
        with filename.open('r') as fp:
            # TODO (GLENN): Harden this step.
            front_lines = []
            is_scanning = False
            for line in fp:
                if line.strip().startswith('/*'):
                    is_scanning = True
                elif line.strip().endswith('*/'):
                    break
                elif is_scanning:
                    front_lines.append(line)
            front_matter = yaml.safe_load('\n'.join(front_lines))

            # TODO (GLENN): Handle large descriptions in embedding model.

            # Build our tool descriptor.
            description = front_matter['Description'].strip()
            return ToolDescriptor(
                identifier=uuid.uuid4(),
                name=front_matter['Name'],
                description=description,
                encoding=self._encode_description(description),
                source=str(filename.absolute()),
                kind=ToolKind.SQLPPQuery,
            )

    def _handle_dot_yaml(self, filename: pathlib.Path) -> ToolDescriptor:
        with filename.open('r') as fp:
            parsed_desc = yaml.safe_load(fp)
        match parsed_desc['Tool Class']:
            case ToolKind.SemanticSearch:
                description = parsed_desc['Description'].strip()
                return ToolDescriptor(
                    identifier=uuid.uuid4(),
                    name=parsed_desc['Name'],
                    description=parsed_desc['Description'].strip(),
                    encoding=self._encode_description(description),
                    source=str(filename.absolute()),
                    kind=ToolKind.SemanticSearch
                )
            case _:
                logger.warning(f'Encountered .yaml file with unknown Tool Class. '
                               f'Not indexing {str(filename.absolute())}.')


class LocalRegistrar(Registrar):
    catalog_file: pathlib.Path

    def index(self, module_locations: typing.List[pathlib.Path]):
        tool_catalog_entries = list()
        for directory in module_locations:
            for member in directory.iterdir():
                match member.suffix:
                    case '.py':
                        for descriptor in self._handle_dot_py(member):
                            tool_catalog_entries.append(descriptor)
                    case '.yaml':
                        from_yaml_tool = self._handle_dot_yaml(member)
                        tool_catalog_entries.append(from_yaml_tool)
                    case '.sqlpp':
                        from_sqlpp_tool = self._handle_dot_sqlpp(member)
                        tool_catalog_entries.append(from_sqlpp_tool)
                    case _:
                        logger.debug(f'Not indexing {str(member.absolute())}.')

        with self.catalog_file.open('w') as fp:
            for entry in tool_catalog_entries:
                fp.write(entry.model_dump_json() + '\n')


class CapellaRegistrar(Registrar):
    pass
