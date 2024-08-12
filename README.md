# rosetta-lc

An agent built with Langchain that accesses tools and Capella for rosetta.

## Rosetta-lc setup

To start, make sure you have `Poetry` installed.

1. Install dependencies 
```bash
poetry install
```

2. Build poetry environment
```bash
poetry build
```

3. Install the .whl file 
```bash
python3 -m pip install dist/rosetta-*.*.*-py3-*-any.whl 
```

## Travel Example

```bash
    python3 example/agentExample.py
```

## Travel Test
```bash
    python3 test/test_agent.py
```