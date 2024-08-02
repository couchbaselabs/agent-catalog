import enum


class ToolKind(str, enum.Enum):
    PythonFunction = 'python_function'
    SQLPPQuery = 'sqlpp_query'
    SemanticSearch = 'semantic_search'
    HTTPRequest = 'http_request'

    def __str__(self):
        return self.value
