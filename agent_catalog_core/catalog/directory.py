import fnmatch
import logging
import pathlib
import typing

logger = logging.getLogger(__name__)


class ScanDirectoryOpts:
    unwanted_patterns: typing.Iterable[str]
    ignore_file_name: typing.Iterable[str]
    ignore_file_parser_factory: typing.Callable[[str], typing.Callable]

    def __init__(self, unwanted_patterns=None, ignore_file_name=None, ignore_file_parser_factory=None):
        self.unwanted_patterns = unwanted_patterns
        self.ignore_file_name = ignore_file_name
        self.ignore_file_parser_factory = ignore_file_parser_factory


def scan_directory(
    root_dir: str, wanted_patterns: typing.Iterable[str], opts: ScanDirectoryOpts = None
) -> typing.Iterable[pathlib.Path]:
    """
    Find file paths in a directory tree which match wanted glob patterns, while also handling any ignore
    config files (like ".gitignore" files) that are encountered in the directory tree.
    """

    ignore_file_parser = None
    if opts:
        ignore_file_path = pathlib.Path(root_dir) / opts.ignore_file_name
        if ignore_file_path.exists() and opts.ignore_file_parser_factory:
            ignore_file_parser = opts.ignore_file_parser_factory(ignore_file_path.absolute())

    for path in pathlib.Path(root_dir).rglob("*"):
        if ignore_file_parser and ignore_file_parser(path):
            logger.debug(f"Ignoring file {path.absolute()}.")
            continue
        if opts and any(fnmatch.fnmatch(path, p) for p in opts.unwanted_patterns or []):
            logger.debug(f"Ignoring file {path.absolute()}.")
            continue
        if path.is_file() and any(fnmatch.fnmatch(path, p) for p in wanted_patterns):
            yield path


if __name__ == "__main__":
    import sys

    # Ex: python3 agentc/core/catalog/directory.py "*.py" "*.md"
    for x in scan_directory("", sys.argv[1:]):
        print(x)
