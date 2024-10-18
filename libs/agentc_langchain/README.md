# Couchbase Agent Catalog LangChain

This package holds a collection of LangChain-specific classes and functions to be used with Agent Catalog.
This package currently includes i) a LangChain agent that interfaces with Capella for its LLM calls and ii) a LangChain
hook for the Couchbase Agent Catalog auditor.

## Examples with LangChain

### Travel Example
We provide an example of a LangChain agent that uses the iQ-backed chat model in the [`examples/`](examples) directory.

To run this example, execute the following:
```bash
python3 example/example_agent.py
```
