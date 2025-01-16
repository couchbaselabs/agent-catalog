import fnmatch
import logging
import pathlib
import typing

logger = logging.getLogger(__name__)


class ScanDirectoryOpts(typing.TypedDict):
    unwanted_patterns: typing.Optional[typing.Iterable[str]]
    ignore_file_names: typing.Optional[typing.Iterable[str]]
    ignore_file_parser_factory: typing.Optional[typing.Callable[[str], typing.Callable]]


def scan_directory(
    root_dir: str, wanted_patterns: typing.Iterable[str], opts: ScanDirectoryOpts = None
) -> typing.Iterable[pathlib.Path]:
    """
    Find file paths in a directory tree which match wanted glob patterns, while also handling any ignore
    config files (like ".gitignore" files) that are encountered in the directory tree.
    """

    ignore_file_parsers = []
    if opts:
        for ignore_file_name in opts["ignore_file_names"]:
            ignore_file_path = pathlib.Path(root_dir) / ignore_file_name
            if ignore_file_path.exists() and opts["ignore_file_parser_factory"]:
                ignore_file_parsers.append(opts["ignore_file_parser_factory"](ignore_file_path.absolute()))

    for path in pathlib.Path(root_dir).rglob("*"):
        if len(ignore_file_parsers) > 0 and any(ignore_file_parser(path) for ignore_file_parser in ignore_file_parsers):
            logger.debug(f"Ignoring file {path.absolute()}.")
            continue
        if opts and any(fnmatch.fnmatch(path, p) for p in opts["unwanted_patterns"] or []):
            logger.debug(f"Ignoring file {path.absolute()}.")
            continue
        if path.is_file() and any(fnmatch.fnmatch(path, p) for p in wanted_patterns):
            yield path


if __name__ == "__main__":
    import sys

    # Ex: python3 agentc_core/catalog/directory.py "*.py" "*.md"
    for x in scan_directory("", sys.argv[1:]):
        print(x)
