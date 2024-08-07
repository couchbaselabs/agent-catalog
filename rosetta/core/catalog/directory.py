import fnmatch
import pathlib
import logging
import typing
import gitignore_parser

logger = logging.getLogger(__name__)

DEFAULT_UNWANTED_PATTERNS = frozenset([
    ".git"
])
DEFAULT_IGNORE_FILE_NAME = ".gitignore"
DEFAULT_IGNORE_PARSER = gitignore_parser.parse_gitignore


def scan_directory(root_dir: str, wanted_patterns: typing.Iterable[str],
                   unwanted_patterns: typing.Iterable[str] = DEFAULT_UNWANTED_PATTERNS,
                   ignore_file_name: typing.Iterable[str] = DEFAULT_IGNORE_FILE_NAME,
                   ignore_file_parser_factory: typing.Callable[[str], typing.Callable] = DEFAULT_IGNORE_PARSER
                   ) -> typing.Iterable[pathlib.Path]:
    """
    Find file paths in a directory tree which match wanted glob patterns, while also handling any ignore
    config files (like ".gitignore" files) that are encountered in the directory tree.
    """

    ignore_file_path = pathlib.Path(root_dir) / ignore_file_name
    if ignore_file_path.exists():
        ignore_file_parser = ignore_file_parser_factory(ignore_file_path.absolute())
    else:
        ignore_file_parser = None

    for path in pathlib.Path(root_dir).rglob('*'):
        if ignore_file_parser and ignore_file_parser(path):
            logger.debug(f'Ignoring file {path.absolute()}.')
            continue
        if any(fnmatch.fnmatch(path, p) for p in unwanted_patterns):
            logger.debug(f'Ignoring file {path.absolute()}.')
            continue
        if path.is_file():
            if any(fnmatch.fnmatch(path, p) for p in wanted_patterns):
                yield path


if __name__ == "__main__":
    import sys

    # Ex: python3 rosetta/core/catalog/directory.py "*.py" "*.md"
    for x in scan_directory(".", sys.argv[1:]):
        print(x)
