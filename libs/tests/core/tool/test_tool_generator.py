import datetime
import importlib
import inspect
import pathlib
import sys
import tempfile
import uuid

from agent_catalog_core.tool.decorator import is_tool
from agent_catalog_core.tool.descriptor.models import HTTPRequestToolDescriptor
from agent_catalog_core.tool.descriptor.models import SemanticSearchToolDescriptor
from agent_catalog_core.tool.descriptor.models import SQLPPQueryToolDescriptor
from agent_catalog_core.tool.generate.generator import HTTPRequestCodeGenerator
from agent_catalog_core.tool.generate.generator import SemanticSearchCodeGenerator
from agent_catalog_core.tool.generate.generator import SQLPPCodeGenerator
from agent_catalog_core.version.identifier import VersionDescriptor
from agent_catalog_core.version.identifier import VersionSystem


def _get_tool_descriptor_factory(cls, filename: pathlib.Path):
    filename_prefix = pathlib.Path(__file__).parent / "resources"
    factory_args = {
        "filename": filename_prefix / filename,
        "version": VersionDescriptor(
            identifier=uuid.uuid4().hex,
            version_system=VersionSystem.Raw,
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc),
        ),
    }
    return cls(**factory_args)


def test_sqlpp_generator():
    # TODO (GLENN): Establish a mock CB instance and execute the generated code.
    positive_1_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/positive_1.sqlpp")
    )
    positive_1_generator = SQLPPCodeGenerator(record_descriptors=list(positive_1_factory))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        generated_files = []
        for code in positive_1_generator.generate():
            new_file = tmp_dir_path / (uuid.uuid4().hex + ".py")
            with new_file.open("w") as fp:
                fp.write(code)
                fp.flush()
            generated_files.append(new_file)
        assert len(generated_files) == 1

        sys.path.append(tmp_dir)
        mod = importlib.import_module(generated_files[0].stem)
        members = inspect.getmembers(mod)
        assert any(x[0] == "ArgumentInput" for x in members)
        assert any(x[0] == "ToolOutput" for x in members)
        assert any(x[0] == "tool_1" for x in members)
        tool = [x[1] for x in members if x[0] == "tool_1"][0]
        assert is_tool(tool)
        sys.path.remove(tmp_dir)


def test_semantic_search_generator():
    # TODO (GLENN): Establish a mock CB instance and execute the generated code.
    positive_1_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/positive_1.yaml")
    )
    positive_1_generator = SemanticSearchCodeGenerator(record_descriptors=list(positive_1_factory))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        generated_files = []
        for code in positive_1_generator.generate():
            new_file = tmp_dir_path / (uuid.uuid4().hex + ".py")
            with new_file.open("w") as fp:
                fp.write(code)
                fp.flush()
            generated_files.append(new_file)
        assert len(generated_files) == 1

        sys.path.append(tmp_dir)
        mod = importlib.import_module(generated_files[0].stem)
        members = inspect.getmembers(mod)
        assert any(x[0] == "ArgumentInput" for x in members)
        assert any(x[0] == "get_travel_blog_snippets_from_user_interests" for x in members)
        tool = [x[1] for x in members if x[0] == "get_travel_blog_snippets_from_user_interests"][0]
        assert is_tool(tool)
        sys.path.remove(tmp_dir)


def test_http_request_generator():
    # TODO (GLENN): Establish a mock HTTP endpoint and execute the generated code.
    positive_1_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/positive_1.yaml")
    )
    positive_1_generator = HTTPRequestCodeGenerator(record_descriptors=list(positive_1_factory))
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = pathlib.Path(tmp_dir)
        generated_files = []
        for code in positive_1_generator.generate():
            new_file = tmp_dir_path / (uuid.uuid4().hex + ".py")
            with new_file.open("w") as fp:
                fp.write(code)
                fp.flush()
            generated_files.append(new_file)
        assert len(generated_files) == 2

        sys.path.append(tmp_dir)
        for file in generated_files:
            mod = importlib.import_module(file.stem)
            members = inspect.getmembers(mod)
            assert any(x[0] == "ArgumentInput" for x in members)
            names = {"create_new_member_create_post", "get_member_rewards_rewards__member_id__get"}
            assert any(x[0] in names for x in members)
            tool = [x[1] for x in members if x[0] in names][0]
            assert is_tool(tool)
        sys.path.remove(tmp_dir)
