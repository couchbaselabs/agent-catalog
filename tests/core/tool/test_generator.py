import pathlib
import sys
import tempfile
import inspect
import importlib
import uuid

from rosetta.core.tool.generate.generator import (
    SQLPPCodeGenerator,
    SemanticSearchCodeGenerator,
    HTTPRequestCodeGenerator
)
from rosetta.core.tool.decorator import ToolMarker
from rosetta.core.tool.descriptor.models import (
    SQLPPQueryToolDescriptor,
    SemanticSearchToolDescriptor,
    HTTPRequestToolDescriptor
)


def _get_tool_descriptor_factory(cls, filename: pathlib.Path):
    filename_prefix = pathlib.Path(__file__).parent / 'resources'
    factory_args = {
        'filename': filename_prefix / filename,
        'id_generator': lambda s: uuid.uuid4().hex,
        'repo_commit_id': uuid.uuid4().hex
    }
    return cls(**factory_args)


def test_sqlpp_generator():
    # TODO (GLENN): Establish a mock CB instance and execute the generated code.
    positive_1_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory,
        filename=pathlib.Path('sqlpp_query/positive_1.sqlpp')
    )
    positive_1_generator = SQLPPCodeGenerator(record_descriptors=list(positive_1_factory))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        positive_1_generator.generate(output_dir=tmp_dir_path)
        generated_files = list(tmp_dir_path.iterdir())
        assert len(generated_files) == 1

        sys.path.append(tmp_dir)
        mod = importlib.import_module(generated_files[0].stem)
        members = inspect.getmembers(mod)
        assert any(x[0] == '_ArgumentInput' for x in members)
        assert any(x[0] == '_ToolOutput' for x in members)
        assert any(x[0] == 'tool_1' for x in members)
        tool = [x[1] for x in members if x[0] == 'tool_1'][0]
        assert isinstance(tool, ToolMarker)
        sys.path.remove(tmp_dir)


def test_semantic_search_generator():
    # TODO (GLENN): Establish a mock CB instance and execute the generated code.
    positive_1_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory,
        filename=pathlib.Path('semantic_search/positive_1.yaml')
    )
    positive_1_generator = SemanticSearchCodeGenerator(record_descriptors=list(positive_1_factory))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        positive_1_generator.generate(output_dir=tmp_dir_path)
        generated_files = list(tmp_dir_path.iterdir())
        assert len(generated_files) == 1

        sys.path.append(tmp_dir)
        mod = importlib.import_module(generated_files[0].stem)
        members = inspect.getmembers(mod)
        assert any(x[0] == '_ArgumentInput' for x in members)
        assert any(x[0] == 'get_travel_blog_snippets_from_user_interests' for x in members)
        tool = [x[1] for x in members if x[0] == 'get_travel_blog_snippets_from_user_interests'][0]
        assert isinstance(tool, ToolMarker)
        sys.path.remove(tmp_dir)


def test_http_request_generator():
    # TODO (GLENN): Establish a mock HTTP endpoint and execute the generated code.
    positive_1_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory,
        filename=pathlib.Path('http_request/positive_1.yaml')
    )
    positive_1_generator = HTTPRequestCodeGenerator(record_descriptors=list(positive_1_factory))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        positive_1_generator.generate(output_dir=tmp_dir_path)
        generated_files = list(tmp_dir_path.iterdir())
        assert len(generated_files) == 2

        sys.path.append(tmp_dir)
        for file in generated_files:
            mod = importlib.import_module(file.stem)
            members = inspect.getmembers(mod)
            assert any(x[0] == '_ArgumentInput' for x in members)
            names = {'create_new_member_create_post', 'get_member_rewards_rewards__member_id__get'}
            assert any(x[0] in names for x in members)
            tool = [x[1] for x in members if x[0] in names][0]
            assert isinstance(tool, ToolMarker)
        sys.path.remove(tmp_dir)
