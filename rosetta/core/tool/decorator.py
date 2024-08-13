import abc
import functools
import typing


class ToolMarker(abc.ABC):
    @abc.abstractmethod
    def __call__(self, *args, **kwargs):
        pass


def tool(func: typing.Callable) -> typing.Callable:
    class MarkedTool(ToolMarker):
        def __init__(self):
            functools.update_wrapper(self, func)

        def __call__(self, *args, **kwargs):
            return func(*args, **kwargs)

    return MarkedTool()
