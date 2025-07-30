import agentc
import agentc_langgraph.state
import fastapi
import langchain_core.messages
import pydantic
import starlette.responses

from graph import FlightPlanner

app = fastapi.FastAPI()

# The following is shared across sessions for a single worker.
catalog = agentc.Catalog()
checkpointer = agentc_langgraph.state.CheckpointSaver(create_if_not_exists=True)
span = catalog.Span(name="FastAPI")
planner = FlightPlanner(catalog=catalog, span=span)


class ChatRequest(pydantic.BaseModel):
    session_id: str
    user_id: str
    message: str

    # Use the following to yield the intermediate results from each agent.
    include_intermediate: bool


@app.post("/chat")
async def chat(req: ChatRequest):
    # Retrieve our previous state if it exists.
    config = {"configurable": {"thread_id": f"{req.user_id}/{req.session_id}"}}
    checkpoint = checkpointer.get(config)
    if not checkpoint:
        input_state = FlightPlanner.build_starting_state()
    else:
        input_state = checkpoint["channel_values"]
        input_state["is_last_step"] = False

    # Add our request to our state.
    input_state["messages"].append(langchain_core.messages.HumanMessage(req.message))

    # We will stream our response.
    async def planner_stream():
        async for event in planner.astream(
            input=input_state,
            config=config,
            stream_mode="updates",
        ):
            for node_name, output_state in event.items():
                if req.include_intermediate:
                    if node_name == "front_desk_agent" and not output_state["is_last_step"]:
                        yield "\n**Reasoning**: We do not need clarification from the user.\n"
                    elif node_name == "front_desk_agent" and output_state["is_last_step"]:
                        yield "\n**Reasoning**: We need some clarification from the user.\n"
                    elif node_name == "endpoint_finding_agent":
                        yield f"\n**Reasoning**: Endpoints have been identified as {output_state['endpoints']}.\n"
                    elif node_name == "route_finding_agent":
                        yield f"\n**Tool**: The following routes have been found: {output_state['routes']}.\n"
                if output_state["is_last_step"]:
                    yield "\n**Assistant Response**:\n" + output_state["messages"][-1].content + "\n"

    return starlette.responses.StreamingResponse(planner_stream())
