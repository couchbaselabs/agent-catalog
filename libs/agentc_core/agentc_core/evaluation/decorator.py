import typing

_EVAL_MARKER_ATTRIBUTE = "__AGENT_CATALOG_EVAL_MARKER__"


def is_evaluation(func: typing.Any):
    return isinstance(func, typing.Callable) and hasattr(func, _EVAL_MARKER_ATTRIBUTE)


def evaluation(func: typing.Callable):
    func.__AGENT_CATALOG_EVAL_MARKER__ = True
    return func
