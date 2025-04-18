if __name__ == "__main__":
    import agentc
    import graph

    # The Agent Catalog 'catalog' object serves versioned tools and prompts.
    # For a comprehensive list of what parameters can be set here, see the class documentation.
    # Parameters can also be set with environment variables (e.g., bucket = $AGENT_CATALOG_BUCKET).
    _catalog = agentc.Catalog()

    # Start our application.
    _state = graph.FlightPlanner.build_starting_state()
    graph.FlightPlanner(catalog=_catalog).invoke(input=_state)
