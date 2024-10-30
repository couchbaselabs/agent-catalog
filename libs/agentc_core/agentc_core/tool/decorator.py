import typing

_TOOL_MARKER_ATTRIBUTE = "__AGENT_CATALOG_TOOL_MARKER__"
_TOOL_NAME_ATTRIBUTE = "__AGENT_CATALOG_TOOL_NAME__"
_TOOL_DESCRIPTION_ATTRIBUTE = "__AGENT_CATALOG_TOOL_DESCRIPTION__"
_TOOL_ANNOTATIONS_ATTRIBUTE = "__AGENT_CATALOG_TOOL_ANNOTATIONS__"


def is_tool(func: typing.Any):
    return isinstance(func, typing.Callable) and hasattr(func, _TOOL_MARKER_ATTRIBUTE)


def get_annotations(func: typing.Callable) -> dict[str, str]:
    return getattr(func, _TOOL_ANNOTATIONS_ATTRIBUTE, dict())


def get_name(func: typing.Callable) -> str:
    return getattr(func, _TOOL_NAME_ATTRIBUTE, func.__name__)


def get_description(func: typing.Callable) -> str:
    return getattr(func, _TOOL_DESCRIPTION_ATTRIBUTE, func.__doc__)


def tool(
    func: typing.Callable = None,
    *,
    name: str = None,
    description: str = None,
    annotations: typing.Dict[str, str] = None,
):
    def _decorator(inner_func: typing.Callable):
        inner_func.__AGENT_CATALOG_TOOL_MARKER__ = True
        if name is not None:
            inner_func.__AGENT_CATALOG_TOOL_NAME__ = name
        if description is not None:
            inner_func.__AGENT_CATALOG_TOOL_DESCRIPTION__ = description
        if annotations is not None:
            inner_func.__AGENT_CATALOG_TOOL_ANNOTATIONS__ = annotations.copy()
        return inner_func

    # We have three cases to consider...
    has_kw_args = name is not None or description is not None or annotations is not None
    if func is not None and not has_kw_args:
        # #1: A user is using the decorator without any arguments (e.g. @tool).
        func.__AGENT_CATALOG_TOOL_MARKER__ = True
        return func

    elif has_kw_args:
        # #2: A user is specifying arguments (e.g. @tool(name="my_tool")).
        return _decorator

    elif func is None and not has_kw_args:
        # #3: A user is using the decorator without any arguments (but as a function call, e.g. @tool()).
        return _decorator

    else:
        raise ValueError("Invalid usage of @tool decorator!")
