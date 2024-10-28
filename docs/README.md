# Agent Catalog Documentation

## Building the Docs

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

## Contributing to the Docs

For those new to writing in reStructuredText, see [here](https://www.sphinx-doc.org/en/master/usage/restructuredtext/basics.html)
for a quick primer.
When contributing to the docs, please adhere to the following guidelines:

1. For easy (future) editing, please use a new line for each sentence.

   Good:
   ```rst
   This is a sentence.
   This is another sentence.
   ```

   Not Good:
   ```rst
   This is a sentence. This is another sentence.
   ```

2. Make sure that all section lines go to the end of the text.

   Good:
   ```rst
   This is a section title
   =======================
   ```

   Not Good:
   ```rst
   This is a section title
   =====
   ```