import fnmatch
import inspect
import logging
import os
import typing

from agentc_core.catalog.directory import scan_directory
from agentc_core.defaults import DEFAULT_SCAN_DIRECTORY_OPTS
from agentc_core.evaluation.decorator import is_evaluation
from agentc_core.security import import_module

logger = logging.getLogger(__name__)


def _print_and_log(message: str, log_level: int, printer: typing.Callable = None):
    logger.log(log_level, message)
    if printer is not None:
        printer(message)


def evaluate(
    source_dirs: list[str | os.PathLike], name_globs: list[str] = None, printer: typing.Callable = None
) -> list[typing.Any]:
    source_files = list()
    for source_dir in source_dirs:
        source_files += scan_directory(os.getcwd(), source_dir, ["*.py"], opts=DEFAULT_SCAN_DIRECTORY_OPTS)

    results = list()
    for source_file in source_files:
        imported_module = import_module(source_file)
        for name, evaluation in inspect.getmembers(imported_module):
            if not is_evaluation(evaluation) or (name_globs and not any(fnmatch.fnmatch(name, g) for g in name_globs)):
                _print_and_log(f"Skipping {name} in {source_file}.", logging.DEBUG)
                continue

            qualified_name = f"{imported_module.__name__}.{name}"
            source_lines, start_line = inspect.getsourcelines(evaluation)
            _print_and_log(f"Found evaluation '{qualified_name}' at line {start_line}.", logging.DEBUG)
            _print_and_log(f"Evaluation '{qualified_name}' is starting...", logging.INFO, printer)
            try:
                result = getattr(imported_module, name)()
                _print_and_log(f"Evaluation '{qualified_name}' has completed successfully.", logging.INFO, printer)
            except Exception as e:
                _print_and_log(
                    f"Evaluation '{qualified_name}' has failed with exception: {str(e)}.", logging.ERROR, printer
                )
                result = None
            results.append(result)

    return results


if __name__ == "__main__":
    evaluate([os.getcwd()])
