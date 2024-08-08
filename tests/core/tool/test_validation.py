import json
import pathlib
import pytest
import inspect
import yaml
import tempfile
import pydantic
import io

from rosetta.core.tool.types.kind import ToolKind
from rosetta.core.tool.types.model import (
    SQLPPQueryMetadata,
    SemanticSearchMetadata,
    HTTPRequestMetadata
)


@pytest.mark.smoke
def test_sqlpp_front_matter():
    with tempfile.TemporaryDirectory() as tmp_dir:
        fp = open(pathlib.Path(tmp_dir) / 'f1', 'w')
        fp.write("""
            /* 
               some front matter: asd
            */
            should not be seen: asd
            """)
        fp.close()
        front_matter1 = SQLPPQueryMetadata.read_front_matter(pathlib.Path(fp.name))
        assert 'should not be seen' not in front_matter1
        assert 'some front matter' in front_matter1
        assert '/*' not in front_matter1
        assert '*/' not in front_matter1

        fp = open(pathlib.Path(tmp_dir) / 'f2', 'w')
        fp.write("""
            /* 
            some front matter: asd */
            should not be seen: asd
            """)
        fp.close()
        front_matter2 = SQLPPQueryMetadata.read_front_matter(pathlib.Path(fp.name))
        assert 'should not be seen' not in front_matter2
        assert 'some front matter' in front_matter2
        assert '/*' not in front_matter2
        assert '*/' not in front_matter2

        fp = open(pathlib.Path(tmp_dir) / 'f3', 'w')
        fp.write("""
            
            /* 
               some front matter: asd
            */
            should not be seen: asd
            """)
        fp.close()
        front_matter3 = SQLPPQueryMetadata.read_front_matter(pathlib.Path(fp.name))
        assert 'should not be seen' not in front_matter3
        assert 'some front matter' in front_matter3
        assert '/*' not in front_matter3
        assert '*/' not in front_matter3

        fp = open(pathlib.Path(tmp_dir) / 'f4', 'w')
        fp.write("""
            -- some other comments in the front 
            /* 
               some front matter: asd
            */
            should not be seen: asd
            """)
        fp.close()
        front_matter4 = SQLPPQueryMetadata.read_front_matter(pathlib.Path(fp.name))
        assert 'should not be seen' not in front_matter4
        assert 'some other comments in the front' not in front_matter4
        assert 'some front matter' in front_matter4
        assert '/*' not in front_matter4
        assert '*/' not in front_matter4


@pytest.mark.smoke
def test_sqlpp_query():
    file1 = io.StringIO(inspect.cleandoc("""
        name: tool_1
        description: >
            i am a dummy tool
            hello i am a dummy tool
        
        input: >
            {
              "type": "object",
              "properties": {
                "source_airport": { "type": "string" },
                "destination_airport": { "type": "string" }
              }
            }
        
        output: >
            {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "airlines": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "layovers": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "from_airport": { "type": "string" },
                  "to_airport": { "type": "string" }
                }
              }
            }
    """))
    file1_yaml = yaml.safe_load(file1)
    file1_model = SQLPPQueryMetadata.model_validate(file1_yaml)
    assert file1_yaml['name'] == file1_model.name
    assert file1_yaml['description'] == file1_model.description
    input_json = json.loads(file1_model.input)
    assert input_json['type'] == 'object'
    assert input_json['properties']['source_airport']['type'] == 'string'
    assert input_json['properties']['destination_airport']['type'] == 'string'
    output_json = json.loads(file1_model.output)
    assert output_json['type'] == 'array'
    assert output_json['items']['type'] == 'object'
    assert output_json['items']['properties']['airlines']['type'] == 'array'

    file2 = io.StringIO(inspect.cleandoc("""
        name: tool_1
        
        tool_kind: sqlpp_query
        
        description: >
            i am a dummy tool
            hello i am a dummy tool
        
        input: >
            {
              "type": "object",
              "properties": {
                "source_airport": { "type": "string" },
                "destination_airport": { "type": "string" }
              }
            }
        
        output: >
            {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "airlines": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "layovers": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "from_airport": { "type": "string" },
                  "to_airport": { "type": "string" }
                }
              }
            }
    """))
    file2_yaml = yaml.safe_load(file2)
    file2_model = SQLPPQueryMetadata.model_validate(file2_yaml)
    assert file2_yaml['name'] == file2_model.name
    assert file2_yaml['description'] == file2_model.description
    assert file2_model.tool_kind == ToolKind.SQLPPQuery

    file3 = io.StringIO(inspect.cleandoc("""
        name: tool_1
    """))
    file3_yaml = yaml.safe_load(file3)
    with pytest.raises(pydantic.ValidationError):
        SQLPPQueryMetadata.model_validate(file3_yaml)

    file4 = io.StringIO(inspect.cleandoc("""
        name: tool_1

        tool_kind: python_function

        description: >
            i am a dummy tool
            hello i am a dummy tool

        input: >
            {
              "type": "object",
              "properties": {
                "source_airport": { "type": "string" },
                "destination_airport": { "type": "string" }
              }
            }

        output: >
            {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "airlines": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "layovers": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "from_airport": { "type": "string" },
                  "to_airport": { "type": "string" }
                }
              }
            }
    """))
    file4_yaml = yaml.safe_load(file4)
    with pytest.raises(pydantic.ValidationError):
        SQLPPQueryMetadata.model_validate(file4_yaml)

    file5 = io.StringIO(inspect.cleandoc("""
        name: tool 1
        description: >
            i am a dummy tool
            hello i am a dummy tool

        input: >
            {
              "type": "object",
              "properties": {
                "source_airport": { "type": "string" },
                "destination_airport": { "type": "string" }
              }
            }

        output: >
            {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "airlines": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "layovers": {
                    "type": "array",
                    "items": { "type": "string" }
                  },
                  "from_airport": { "type": "string" },
                  "to_airport": { "type": "string" }
                }
              }
            }
    """))
    file6_yaml = yaml.safe_load(file5)
    with pytest.raises(pydantic.ValidationError):
        SQLPPQueryMetadata.model_validate(file6_yaml)


@pytest.mark.smoke
def test_semantic_search():
    file1 = io.StringIO(inspect.cleandoc("""
        tool_kind: semantic_search
        
        name: get_travel_blog_snippets_from_user_interests
        
        description: >
          Fetch snippets of travel blogs using a user's interests.
        
        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }
        
        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
       """))
    file1_yaml = yaml.safe_load(file1)
    file1_model = SemanticSearchMetadata.model_validate(file1_yaml)
    assert file1_yaml['tool_kind'] == file1_model.tool_kind
    assert file1_yaml['description'] == file1_model.description
    input_json = json.loads(file1_model.input)
    assert input_json['type'] == 'object'
    assert input_json['properties']['user_interests']['type'] == 'array'
    assert input_json['properties']['user_interests']['items']['type'] == 'string'
    assert file1_yaml['vector_search']['bucket'] == file1_model.vector_search.bucket
    assert file1_yaml['vector_search']['embedding_model'] == file1_model.vector_search.embedding_model

    file2 = io.StringIO(inspect.cleandoc("""
        tool_kind: semantic_search

        name: get travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file2_yaml = yaml.safe_load(file2)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file2_yaml)

    file3 = io.StringIO(inspect.cleandoc("""
        tool_kind: python_function

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file3_yaml = yaml.safe_load(file3)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file3_yaml)

    file4 = io.StringIO(inspect.cleandoc("""
        tool_kind: python_function

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file4_yaml = yaml.safe_load(file4)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file4_yaml)

    file5 = io.StringIO(inspect.cleandoc("""
        tool_kind: python_function

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file5_yaml = yaml.safe_load(file5)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file5_yaml)


@pytest.mark.smoke
def test_semantic_search():
    file1 = io.StringIO(inspect.cleandoc("""
        tool_kind: semantic_search

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
       """))
    file1_yaml = yaml.safe_load(file1)
    file1_model = SemanticSearchMetadata.model_validate(file1_yaml)
    assert file1_yaml['tool_kind'] == file1_model.tool_kind
    assert file1_yaml['description'] == file1_model.description
    input_json = json.loads(file1_model.input)
    assert input_json['type'] == 'object'
    assert input_json['properties']['user_interests']['type'] == 'array'
    assert input_json['properties']['user_interests']['items']['type'] == 'string'
    assert file1_yaml['vector_search']['bucket'] == file1_model.vector_search.bucket
    assert file1_yaml['vector_search']['embedding_model'] == file1_model.vector_search.embedding_model

    file2 = io.StringIO(inspect.cleandoc("""
        tool_kind: semantic_search

        name: get travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file2_yaml = yaml.safe_load(file2)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file2_yaml)

    file3 = io.StringIO(inspect.cleandoc("""
        tool_kind: python_function

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file3_yaml = yaml.safe_load(file3)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file3_yaml)

    file4 = io.StringIO(inspect.cleandoc("""
        tool_kind: python_function

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
          }

        vector_search:
          bucket: travel-sample
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file4_yaml = yaml.safe_load(file4)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file4_yaml)

    file5 = io.StringIO(inspect.cleandoc("""
        tool_kind: python_function

        name: get_travel_blog_snippets_from_user_interests

        description: >
          Fetch snippets of travel blogs using a user's interests.

        input: >
          {
            "type": "object",
            "properties": {
              "user_interests": {
                "type": "array",
                "items": { "type": "string" }
              }
            }
          }

        vector_search:
          scope: inventory
          collection: article
          index: articles-index
          vector_field: vec
          text_field: text
          embedding_model: sentence-transformers/all-MiniLM-L12-v2
           """))
    file5_yaml = yaml.safe_load(file5)
    with pytest.raises(pydantic.ValidationError):
        SemanticSearchMetadata.model_validate(file5_yaml)


@pytest.mark.smoke
def test_http_request():
    filename_prefix = pathlib.Path(__file__).parent.absolute()
    file1 = io.StringIO(inspect.cleandoc(f"""
        tool_kind: http_request
        
        open_api:
          filename: {filename_prefix}/_good_spec.json
          operations:
            - path: /create
              method: post
            - path: /rewards/{{member_id}}
              method: get
         """))
    file1_yaml = yaml.safe_load(file1)
    file1_model = HTTPRequestMetadata.model_validate(file1_yaml)
    assert file1_yaml['tool_kind'] == file1_model.tool_kind
    assert file1_yaml['open_api']['filename'] == file1_model.open_api.filename
    assert file1_yaml['open_api']['operations'][0]['path'] == file1_model.open_api.operations[0].path
    assert file1_yaml['open_api']['operations'][0]['method'] == file1_model.open_api.operations[0].method
    assert file1_yaml['open_api']['operations'][1]['path'] == file1_model.open_api.operations[1].path
    assert file1_yaml['open_api']['operations'][1]['method'] == file1_model.open_api.operations[1].method

    file2 = io.StringIO(inspect.cleandoc(f"""
        tool_kind: python_function

        open_api:
          filename: {filename_prefix}/_good_spec.json
          operations:
            - path: /create
              method: post
            - path: /rewards/{{member_id}}
              method: get
         """))
    file2_yaml = yaml.safe_load(file2)
    with pytest.raises(pydantic.ValidationError):
        HTTPRequestMetadata.model_validate(file2_yaml)

    file3 = io.StringIO(inspect.cleandoc(f"""
        tool_kind: http_request

        open_api:
          filename: {filename_prefix}/_good_spec.json
          operations:
            - path: /create
              method: get
            - path: /rewards/{{member_id}}
              method: get
         """))
    file3_yaml = yaml.safe_load(file3)
    with pytest.raises(pydantic.ValidationError):
        HTTPRequestMetadata.model_validate(file3_yaml)

    file3 = io.StringIO(inspect.cleandoc(f"""
        tool_kind: http_request

        open_api:
          filename: {filename_prefix}/_good_spec.json
          operations:
            - path: /doesnotexist
              method: post
            - path: /rewards/{{member_id}}
              method: get
         """))
    file3_yaml = yaml.safe_load(file3)
    with pytest.raises(pydantic.ValidationError):
        HTTPRequestMetadata.model_validate(file3_yaml)

    file4 = io.StringIO(inspect.cleandoc(f"""
        tool_kind: http_request

        open_api:
          filename: {filename_prefix}/_bad_spec.json
          operations:
            - path: /create
              method: post
         """))
    file4_yaml = yaml.safe_load(file4)
    with pytest.raises(pydantic.ValidationError):
        HTTPRequestMetadata.model_validate(file4_yaml)

    file5 = io.StringIO(inspect.cleandoc(f"""
        tool_kind: http_request

        open_api:
          filename: {filename_prefix}/_bad_spec.json
          operations:
            - path: /rewards/{{member_id}}
              method: get
         """))
    file5_yaml = yaml.safe_load(file5)
    with pytest.raises(pydantic.ValidationError):
        HTTPRequestMetadata.model_validate(file5_yaml)
