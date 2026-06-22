# Couchbase Agent Catalog

Couchbase Agent Catalog is a toolkit for managing the moving parts of an AI agent. Its tools and prompts become versioned, discoverable, monitored assets rather than strings buried in your application code.
The Agent Catalog ships as a Python SDK and a companion command-line tool, and uses Couchbase Enterprise or a Couchbase Capella cluster as the backing store for your catalog and agent activity logs.
It is framework-agnostic. Use it with LangChain, LangGraph, LlamaIndex, or your own orchestration layer, alongside whichever LLM you prefer.

## Production-ready agentic apps

Most agents in the wild are assembled from loosely coupled parts: prompts live in one file, tool definitions in another, traces are logged inconsistently (if at all), and there's no clean way to answer "which prompt or tool produced this behavior?" That makes agents hard to debug, hard to evolve, and hard to trust in production.
Agent Catalog addresses that by giving you one place to:
- **Define tools and prompts as managed records**. Author them locally, then index and publish them to your Couchbase cluster as versioned assets — no more hardcoded prompt strings that can't be tracked or rolled back.
- **Discover tools semantically at runtime**. Instead of wiring every tool into every agent by hand, search a catalog of hundreds of tools by the question you're trying to answer. This keeps an agent's working tool set small, which improves accuracy and lowers token cost.
- **Observe what your agent actually did**. Capture structured traces of agent activity so you can analyze prompt and tool usage, debug decisions, and measure quality over time — queryable with SQL++ directly in Couchbase.
- **Version everything with your code**. Catalog records are tied to your Git state, so a published catalog corresponds to a known commit.

## What's in the box
- Tool & prompt catalog: Versioned, centralized, reusable definitions shared across teams.
- Semantic Discovery: Search large tool/prompt sets by intent rather than wiring them manually.
- Agent Tracing: Structured, queryable activity logs for debugging and evaluation.
- Framework Integrations: First-class helpers for LangChain, LangGraph, and LlamaIndex.
- CLI + SDK: Manage the catalog from the command line; consume it from Python.
