import fnmatch
import logging
import os
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
    all_ignore_files_paths = []
    if opts:
        current_dir = os.getcwd()
        user_target_dir = os.path.abspath(os.path.join(current_dir, root_dir))
        # Find all ignore files in the directory tree till user mentioned directory.
        for root, _dirs, files in os.walk(current_dir):
            # Ignore path if it does not appear in the path towards user mentioned directory.
            if root not in user_target_dir:
                continue

            for file in files:
                if file in opts["ignore_file_names"]:
                    all_ignore_files_paths.append(os.path.join(root, file))

            # Stop crawling once user mentioned directory is crawled.
            if root == user_target_dir:
                break

        if opts["ignore_file_parser_factory"]:
            for ignore_file_path in all_ignore_files_paths:
                ignore_file_parsers.append(opts["ignore_file_parser_factory"](ignore_file_path))

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
