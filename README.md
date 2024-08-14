# rosetta

User facing repository for all things rosetta (tooling around agent workflows).

## Getting Started

(TODO: We need to upload this to PyPI somehow)

1. Ensure that you have `python3.11` installed.
2. Use `pip` to install `rosetta`.
   ```bash
   pip install rosetta
   ```
3. You should now have the `rosetta` command line tool installed.
   Run the `rosetta` command to test your installation.
   ```bash
    Usage: rosetta [OPTIONS] COMMAND [ARGS]...
    
      A command line tool for Rosetta.
    
    Options:
      -c, --catalog DIRECTORY   Directory of local catalog files. The local
                                catalog DIRECTORY should be checked into git.
                                [default: .rosetta-catalog]
      -a, --activity DIRECTORY  Directory of local activity files (runtime data).
                                The local activity DIRECTORY should NOT be checked
                                into git, as it holds runtime activity data like
                                logs, etc.  [default: .rosetta-activity]
      -v, --verbose             Enable verbose output.
      --help                    Show this message and exit.
    
    Commands:
      clean       Clean up the catalog folder, the activity folder, any...
      env         Show this program's environment or configuration parameters...
      find        Find tools, prompts, etc.
      index       Walk the source directory trees (SOURCE_DIRS) to index...
      publish     Publish the local catalog to a Couchbase instance.
      status      Show the status of the local catalog.
      version     Show the version of this tool.
      web         Start a local web server to view our tools.
   ```

## Building From Source

1. Ensure that you have `python3.11` and `poetry` installed.
   ```bash
   python3 -m pip install poetry
   ```
2. Clone this repository -- make sure that you have an SSH key setup!
   ```bash
   git clone git@github.com:couchbaselabs/rosetta.git
   ```
3. Install the dependencies from `pyproject.toml`.
   ```bash
   poetry install
   ```

For examples on what an agentic workflow with Rosetta looks like, see
the [rosetta-example](https://github.com/couchbaselabs/rosetta-example) repository.

## For Contributors / Developers

### On Child Repositories

At the moment, there exists two child repositories:

1. [`rosetta-core`](https://github.com/couchbaselabs/rosetta-core), which implements the core functionality of
   `rosetta` in an "un-opinionated" manner, and...
2. [`rosetta-lc`](https://github.com/couchbaselabs/rosetta-example), which supplies additional tooling around building
   LangChain-specific agents.

This repository (`rosetta`) is meant to serve as a "front-desk", where we focus on _setting defaults_
(i.e., being opinionated) for the sake of a simpler / more-user-friendly out-of-the-box experience.
Keep this in mind when contributing to these repositories: the core should be minimal and extensible, and this
repository should leverage the core's extensibility.

### Enabling Debug Mode

To enable debug mode, execute the following command:

```bash
export ROSETTA_DEBUG=1
```

