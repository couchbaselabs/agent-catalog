# Agent Catalog Command Line Interface

Install the `agentc` package using the instructions in the [README.md](../../README.md)!

## Testing

To run the tests defined in the [`tests`](./tests) folder, execute the following command:

```bash
cd libs/agentc_cli
pytest tests
```

This command will spin up a Docker instance and use the default Couchbase ports, so make sure you have no other local
Couchbase instances using ports 8091-8097, 9123, 11207, 11210, 11280, and 18091-18097.
