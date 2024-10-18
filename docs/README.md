# Agent Catalog Documentation

Below are instructions for building the Agent Catalog documentation.

1. Install the top-level project with `poetry install`.
2. Navigate to this directory (`cd docs`).
3. Run `make html` to populate the `build` directory.
4. Serve the `build` directory with Python's built-in HTTP server:

   ```bash
   cd build
   python -m http.server
   ```

   Or (if you are making active documentation changes), use `sphinx-autobuild`:

   ```bash
   sphinx-autobuild source build
   ```

   In both cases, you can now navigate to http://localhost:8000 and navigate the docs!