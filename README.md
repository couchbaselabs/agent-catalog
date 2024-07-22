# rosetta-core

The core for a Couchbase-backed agentic workflow SDK.

## Building From Source

1. Ensure that you have `python3.11` and `poetry` installed.
   ```bash
   python3 pip install poetry
   ```
2. Clone this repository -- make sure that you have an SSH key setup!
    ```bash
    git clone git@github.com:couchbaselabs/rosetta-core.git
    ```
3. Install the dependencies from `pyproject.toml`.
   ```bash
   poetry install 
   ```
4. You should now have the `rosetta` command line tool installed.
   Run the `init` command to download a default SBERT model and test your installation.
   ```bash
   rosetta init
   ```
5. To build a `.whl` file for distribution, run the command below.
   Your `.whl` file will show up under the `dist` folder.
   ```bash
   poetry build
   ```

   .
   .
   .

Once you have the `.whl` file, use `pip` to install this `rosetta` build in another project to define agentic workflows!
```bash
pip install dist/rosetta-*.*.*-py3-*-any.whl
```
For examples on what an agentic workflow with Rosetta looks like, see
the [rosetta-sample](https://github.com/couchbaselabs/rosetta-sample) repository.
