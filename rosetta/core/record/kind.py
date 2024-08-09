import enum


class RecordKind(enum.StrEnum):
    PythonFunction = 'python_function'
    SQLPPQuery = 'sqlpp_query'
    SemanticSearch = 'semantic_search'
    HTTPRequest = 'http_request'

    # TODO (GLENN): Include other classes for prompts.