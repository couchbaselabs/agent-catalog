import pytest

from agentc_core.remote.util.query import quote_sql_identifier
from agentc_core.remote.util.query import quote_sql_keyspace


def test_quote_sql_identifier_escapes_backticks():
    assert quote_sql_identifier("bucket`)name") == "`bucket``)name`"


def test_quote_sql_keyspace_quotes_all_parts():
    assert quote_sql_keyspace("bucket", "scope", "collection") == "`bucket`.`scope`.`collection`"


def test_quote_sql_identifier_rejects_empty_string():
    with pytest.raises(ValueError):
        quote_sql_identifier("")
