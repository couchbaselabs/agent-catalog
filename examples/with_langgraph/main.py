if __name__ == "__main__":
    import agentc
    import graph
    import node

    # The Agent Catalog 'catalog' object serves versioned tools and prompts.
    # For a comprehensive list of what parameters can be set here, see the class documentation.
    # Parameters can also be set with environment variables (e.g., bucket = $AGENT_CATALOG_BUCKET).
    _catalog = agentc.Catalog()

    # Start our application.
    state = node.State(
        messages=[], endpoints=None, routes=None, needs_clarification=False, is_last_step=False, previous_node=None
    )
    graph.FlightPlanner(catalog=_catalog).invoke(input=state)
