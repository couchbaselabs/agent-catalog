import agentc
import agentc.auditor
import agentc.langchain
import agentc.provider
import controlflow
import controlflow.events
import controlflow.orchestration
import controlflow.tools
import dotenv
import langchain_openai
import os
import pydantic
import uuid

from utils import TaskFactory

# Make sure you populate your .env file with the correct credentials!
dotenv.load_dotenv()

# The Agent Catalog provider serves versioned tools and prompts.
# For a comprehensive list of what parameters can be set here, see the class documentation.
# Parameters can also be set with environment variables (e.g., bucket = $AGENT_CATALOG_BUCKET).
provider = agentc.Provider(
    # This 'decorator' parameter tells us how tools should be returned (in this case, as a ControlFlow tool).
    decorator=lambda t: controlflow.tools.Tool.from_function(t.func),
    # Below, we define parameters that are passed to tools at runtime.
    # The 'keys' of this dictionary map to the values in various tool definitions (e.g., blogs_from_interests.yaml).
    # The 'values' of this dictionary map to actual values required by the tool.
    # In this case, we get the Couchbase connection string, username, and password from environment variables.
    secrets={
        "CB_CONN_STRING": os.getenv("CB_CONN_STRING"),
        "CB_USERNAME": os.getenv("CB_USERNAME"),
        "CB_PASSWORD": os.getenv("CB_PASSWORD"),
    },
)

# The Agent Catalog auditor will bind all LLM messages to...
# 1. a specific catalog snapshot (i.e., the version of the catalog when the agent was started), and
# 2. a specific conversation thread / session (passed in via session=thread_id).
# Note: similar to a Rosetta provider, the parameters of a Rosetta auditor can be set with environment variables.
auditor = agentc.Auditor(llm_name="gpt-4o")
chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0)


def run_flow(thread_id: str):
    # We provide a LangChain specific decorator (agentc.langchain.audit) to inject this auditor into ChatModels.
    starter_agent = controlflow.Agent(
        name="Starter Agent",
        model=agentc.langchain.audit(chat_model, session=thread_id, auditor=auditor),
    )

    # We need to explicitly provide a mechanism for our agent to communicate with the user.
    def talk_to_user(message: str, get_response: bool = True) -> str:
        """
        Send a message to the human user and optionally wait for a response. If `get_response` is True, the function
        will return the user's response, otherwise it will return a simple confirmation. Do not send the user
        concurrent messages that require responses, as this will cause confusion.

        You may need to ask the human about multiple tasks at once. Consolidate your questions into a single message.
        For example, if Task 1 requires information X and Task 2 needs information Y, send a single message that
        naturally asks for both X and Y.
        """
        auditor.accept(kind=agentc.auditor.Kind.Assistant, content=message, session=thread_id)
        if get_response:
            response = input(message)
            auditor.accept(kind=agentc.auditor.Kind.Human, content=response, session=thread_id)
            return response
        return "Message sent to user."

    # Below, we have a helper class that removes some of the boilerplate for using Agent Catalog + ControlFlow.
    task_factory = TaskFactory(
        auditor=auditor,
        session=thread_id,
        agent=starter_agent,
        tools=[talk_to_user],
    )

    # It is highly recommended that you define types while building your agent (both for your tools and tasks).
    class EndpointsType(pydantic.BaseModel):
        source_airport: str
        dest_airport: str

    # Write your agent logic (i.e., task graph) here!
    while True:
        endpoints = task_factory.run(
            # Search for prompts using your provider.
            prompt=provider.get_prompt_for(query="asking for source and destination airports"),
            # All other arguments are forwarded to the ControlFlow Task constructor.
            # Check out their docs here: https://controlflow.ai/concepts/tasks#task-properties
            result_type=EndpointsType,
        )

        # We "draw" implicit dependency edges by using the results of previous tasks.
        # In this example, all tasks are executed eagerly (though there is some limited support for lazy evaluation).
        travel_routes = task_factory.run(
            prompt=provider.get_prompt_for(query="finding routes between airports"),
            context={"source_airport": endpoints.source_airport, "destination_airport": endpoints.dest_airport},
            result_type=str,
        )
        print(f"Your routes are: {travel_routes}")
        is_continue = task_factory.run(
            prompt=provider.get_prompt_for(query="after addressing a user's request"), result_type=[True, False]
        )
        if not is_continue:
            break


if __name__ == "__main__":
    run_flow(thread_id=uuid.uuid4().hex)
