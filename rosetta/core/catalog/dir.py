import fnmatch
import os

import gitignore_parser


DEFAULT_UNWANTED_PATTERNS = [".git"]
DEFAULT_IGNORE_FILE_NAME = ".gitignore"
DEFAULT_IGNORE_PARSER = gitignore_parser.parse_gitignore


def dir_scan(root_dir,
             wanted_patterns,
             unwanted_patterns=DEFAULT_UNWANTED_PATTERNS,
             ignore_file_name=DEFAULT_IGNORE_FILE_NAME,
             ignore_file_parser=DEFAULT_IGNORE_PARSER):
    """Recursively find file paths in a directory tree which
       match wanted glob patterns, while also handling any ignore
       config files (like ".gitignore" files) that are encountered
       in the directory tree.
    """

    def ignore_file_parse(dir):
        ignore_file_path = os.path.join(dir, ignore_file_name)
        if os.path.exists(ignore_file_path):
            return ignore_file_parser(ignore_file_path)

        return None

    def dir_scan_recur(current_dir, ignore_fn):
        for entry in os.scandir(current_dir):
            if ignore_fn and ignore_fn(entry.path):
                continue

            if any(fnmatch.fnmatch(entry.name, p) for p in unwanted_patterns):
                continue

            if entry.is_dir():
                yield from dir_scan_recur(entry.path,
                                          ignore_file_parse(entry.path) or ignore_fn)

            elif entry.is_file():
                if any(fnmatch.fnmatch(entry.name, p) for p in wanted_patterns):
                    yield entry.path

    return list(dir_scan_recur(root_dir, ignore_file_parse(root_dir)))


if __name__ == "__main__":
    import sys

    # Ex: python3 rosetta/core/catalog/dir.py "*.py" "*.md"
    for x in dir_scan(".", sys.argv[1:]):
        print(x)
