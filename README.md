# rosetta-lc

A collection of LangChain-specific classes and functions to be used with [rosetta-core](https://github.com/couchbaselabs/rosetta-core). 
This package currently includes a LangChain agent that interfaces with Capella for its LLM calls.

## Building From Source

1. To start, make sure you have `python3` and `poetry` installed.
    ```bash
    python3 -m pip install poetry
    ```
2. Clone this repository -- make sure that you have an SSH key setup!
    ```bash
    git clone git@github.com:couchbaselabs/rosetta-lc.git
    ```
3. Download the project dependencies from `pyproject.toml` using `poetry`. 
    ```bash
    poetry install
    ```
4. Build a `.whl` file using `poetry`.
   ```bash
   poetry build
   ```
   You should end up with a generated `dist` directory containing a `.whl` file.
   To install this `.whl` file in another project, use `pip install`.
   ```bash
    python3 -m pip install dist/rosetta-*.*.*-py3-*-any.whl 
   ```

## Examples with LangChain

### Travel Example
We provide an example of a LangChain agent in the `example` directory.
To run this example, execute the following:
```bash
python3 example/agentExample.py
```
