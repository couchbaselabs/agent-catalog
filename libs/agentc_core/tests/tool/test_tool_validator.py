import datetime
import json
import pathlib
import pydantic
import pytest
import uuid

from agentc_core.record.descriptor import RecordKind
from agentc_core.tool.descriptor.models import HTTPRequestToolDescriptor
from agentc_core.tool.descriptor.models import PythonToolDescriptor
from agentc_core.tool.descriptor.models import SemanticSearchToolDescriptor
from agentc_core.tool.descriptor.models import SQLPPQueryToolDescriptor
from agentc_core.version.identifier import VersionDescriptor
from agentc_core.version.identifier import VersionSystem


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


@pytest.mark.smoke
def test_python_function():
    positive_1_factory = _get_tool_descriptor_factory(
        cls=PythonToolDescriptor.Factory, filename=pathlib.Path("python_function/positive_1.py")
    )
    positive_1_tools = list(positive_1_factory)
    assert len(positive_1_tools) == 1
    assert positive_1_tools[0].name == "calculate_travel_costs"
    assert (
        "Calculate the travel costs based on distance, fuel efficiency, and fuel price."
        in positive_1_tools[0].description
    )

    positive_2_factory = _get_tool_descriptor_factory(
        cls=PythonToolDescriptor.Factory, filename=pathlib.Path("python_function/positive_2.py")
    )
    positive_2_tools = list(positive_2_factory)
    assert len(positive_2_tools) == 1
    assert positive_2_tools[0].name == "calculate_travel_costs"
    assert (
        "Calculate the travel costs based on distance, fuel efficiency, and fuel price."
        in positive_2_tools[0].description
    )

    positive_3_factory = _get_tool_descriptor_factory(
        cls=PythonToolDescriptor.Factory, filename=pathlib.Path("python_function/positive_3.py")
    )
    positive_3_tools = list(positive_3_factory)
    assert len(positive_3_tools) == 1
    assert positive_3_tools[0].name == "calculate_travel_costs_1"
    assert "Calculate something" in positive_3_tools[0].description
    assert positive_3_tools[0].annotations["a"] == "1"
    assert positive_3_tools[0].annotations["b"] == "2"


@pytest.mark.smoke
def test_sqlpp_query():
    positive_1_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/positive_1.sqlpp")
    )
    positive_1_tools = list(positive_1_factory)
    assert len(positive_1_tools) == 1
    assert positive_1_tools[0].name == "tool_1"
    assert positive_1_tools[0].record_kind == RecordKind.SQLPPQuery
    assert "SELECT 1;" in positive_1_tools[0].query
    assert "i am a dummy tool" in positive_1_tools[0].description
    assert "hello i am a dummy tool" in positive_1_tools[0].description
    assert positive_1_tools[0].secrets[0].couchbase.conn_string == "CB_CONN_STRING"
    assert positive_1_tools[0].secrets[0].couchbase.username == "CB_USERNAME"
    assert positive_1_tools[0].secrets[0].couchbase.password == "CB_PASSWORD"
    positive_1_input_json = json.loads(positive_1_tools[0].input)
    assert positive_1_input_json["type"] == "object"
    assert positive_1_input_json["properties"]["source_airport"]["type"] == "string"
    assert positive_1_input_json["properties"]["destination_airport"]["type"] == "string"
    positive_1_output_json = json.loads(positive_1_tools[0].output)
    assert positive_1_output_json["type"] == "array"
    assert positive_1_output_json["items"]["type"] == "object"
    assert positive_1_output_json["items"]["properties"]["airlines"]["type"] == "array"

    # Test the optional inclusion of record_kind.
    positive_2_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/positive_2.sqlpp")
    )
    positive_2_tools = list(positive_2_factory)
    assert len(positive_2_tools) == 1
    assert positive_2_tools[0].name == "tool_1"
    assert positive_2_tools[0].record_kind == RecordKind.SQLPPQuery
    assert "SELECT 1;" in positive_2_tools[0].query
    assert "i am a dummy tool" in positive_2_tools[0].description
    assert "hello i am a dummy tool" in positive_2_tools[0].description
    assert positive_2_tools[0].secrets[0].couchbase.conn_string == "CB_CONN_STRING"
    assert positive_2_tools[0].secrets[0].couchbase.username == "CB_USERNAME"
    assert positive_2_tools[0].secrets[0].couchbase.password == "CB_PASSWORD"
    positive_2_input_json = json.loads(positive_2_tools[0].input)
    assert positive_2_input_json["type"] == "object"
    assert positive_2_input_json["properties"]["source_airport"]["type"] == "string"
    assert positive_2_input_json["properties"]["destination_airport"]["type"] == "string"
    positive_2_output_json = json.loads(positive_2_tools[0].output)
    assert positive_2_output_json["type"] == "array"
    assert positive_2_output_json["items"]["type"] == "object"
    assert positive_2_output_json["items"]["properties"]["airlines"]["type"] == "array"

    # Test the exclusion of output.
    positive_3_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/positive_3.sqlpp")
    )
    positive_3_tools = list(positive_3_factory)
    assert len(positive_3_tools) == 1
    assert positive_3_tools[0].name == "tool_1"
    assert positive_3_tools[0].record_kind == RecordKind.SQLPPQuery
    assert "SELECT 1;" in positive_3_tools[0].query
    assert "i am a dummy tool" in positive_3_tools[0].description
    assert "hello i am a dummy tool" in positive_3_tools[0].description
    assert positive_3_tools[0].secrets[0].couchbase.conn_string == "CB_CONN_STRING"
    assert positive_3_tools[0].secrets[0].couchbase.username == "CB_USERNAME"
    assert positive_3_tools[0].secrets[0].couchbase.password == "CB_PASSWORD"
    positive_3_input_json = json.loads(positive_3_tools[0].input)
    assert positive_3_input_json["type"] == "object"
    assert positive_3_input_json["properties"]["source_airport"]["type"] == "string"
    assert positive_3_input_json["properties"]["destination_airport"]["type"] == "string"
    assert positive_3_tools[0].output is None

    # Test an incomplete tool descriptor.
    negative_1_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/negative_1.sqlpp")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_1_factory)

    # Test an incorrect record_kind.
    negative_2_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/negative_2.sqlpp")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_2_factory)

    # Test a bad JSON schema.
    negative_3_factory = _get_tool_descriptor_factory(
        cls=SQLPPQueryToolDescriptor.Factory, filename=pathlib.Path("sqlpp_query/negative_3.sqlpp")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_3_factory)


@pytest.mark.smoke
def test_semantic_search():
    positive_1_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/positive_1.yaml")
    )
    positive_1_tools = list(positive_1_factory)
    assert len(positive_1_tools) == 1
    assert positive_1_tools[0].name == "get_travel_blog_snippets_from_user_interests"
    assert "Fetch snippets of travel blogs using a user's interests." in positive_1_tools[0].description
    assert positive_1_tools[0].secrets[0].couchbase.conn_string == "CB_CONN_STRING"
    assert positive_1_tools[0].secrets[0].couchbase.username == "CB_USERNAME"
    assert positive_1_tools[0].secrets[0].couchbase.password == "CB_PASSWORD"
    assert positive_1_tools[0].record_kind == RecordKind.SemanticSearch
    positive_1_input_json = json.loads(positive_1_tools[0].input)
    assert positive_1_input_json["type"] == "object"
    assert positive_1_input_json["properties"]["user_interests"]["type"] == "array"
    assert positive_1_input_json["properties"]["user_interests"]["items"]["type"] == "string"
    assert positive_1_tools[0].vector_search.bucket == "travel-sample"
    assert positive_1_tools[0].vector_search.scope == "inventory"
    assert positive_1_tools[0].vector_search.collection == "article"

    # Test the serialization of annotations.
    positive_2_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/positive_2.yaml")
    )
    positive_2_tools = list(positive_2_factory)
    assert len(positive_1_tools) == 1
    assert positive_2_tools[0].annotations["just_for_testing"] == "false"
    assert positive_2_tools[0].annotations["gdpr_compliant"] == "true"

    # Test a bad (non-Python-identifier) tool name.
    negative_1_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/negative_1.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_1_factory)

    # Test an incorrect record_kind.
    negative_2_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/negative_2.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_2_factory)

    # Test an invalid input schema (one that is empty).
    negative_3_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/negative_3.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_3_factory)

    # Test a malformed vector_search object.
    negative_4_factory = _get_tool_descriptor_factory(
        cls=SemanticSearchToolDescriptor.Factory, filename=pathlib.Path("semantic_search/negative_4.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_4_factory)


@pytest.mark.smoke
def test_http_request():
    positive_1_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/positive_1.yaml")
    )
    positive_1_tools = list(positive_1_factory)
    assert len(positive_1_tools) == 2
    assert positive_1_tools[0].name == "create_new_member_create_post"
    assert positive_1_tools[0].description == "Create a new travel-rewards member."
    assert positive_1_tools[0].operation.path == "/create"
    assert positive_1_tools[0].operation.method.lower() == "post"
    assert positive_1_tools[0].record_kind == RecordKind.HTTPRequest
    assert positive_1_tools[1].name == "get_member_rewards_rewards__member_id__get"
    assert positive_1_tools[1].description == "Get the rewards associated with a member."
    assert positive_1_tools[1].operation.path == "/rewards/{member_id}"
    assert positive_1_tools[1].operation.method.lower() == "get"
    assert positive_1_tools[1].record_kind == RecordKind.HTTPRequest

    # Test an incorrect record kind.
    negative_1_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/negative_1.yaml")
    )
    with pytest.raises(pydantic.ValidationError):
        list(negative_1_factory)

    # Test a non-existent method for an operation.
    negative_2_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/negative_2.yaml")
    )
    with pytest.raises((pydantic.ValidationError, ValueError)):
        list(negative_2_factory)

    # Test a non-existent path for an operation.
    negative_3_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/negative_3.yaml")
    )
    with pytest.raises((pydantic.ValidationError, ValueError)):
        list(negative_3_factory)

    # Test an operation that doesn't specify an operationId.
    negative_4_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/negative_4.yaml")
    )
    with pytest.raises((pydantic.ValidationError, ValueError)):
        list(negative_4_factory)

    # Test an operation that doesn't specify a description.
    negative_5_factory = _get_tool_descriptor_factory(
        cls=HTTPRequestToolDescriptor.Factory, filename=pathlib.Path("http_request/negative_5.yaml")
    )
    with pytest.raises((pydantic.ValidationError, ValueError)):
        list(negative_5_factory)
