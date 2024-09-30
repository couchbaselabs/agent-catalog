import typing


def is_tool(func: typing.Any):
    return isinstance(func, typing.Callable) and hasattr(func, "__ROSETTA_TOOL_MARKER__")


# TODO (GLENN): Extend this to support a decorator factory (see LangChain or ControlFlow for examples)...?
# TODO (GLENN): Add some validation to check if a docstring exists.
def tool(func: typing.Callable):
    func.__ROSETTA_TOOL_MARKER__ = True
    return func
