import agentc
import agentc_langchain
import controlflow
import controlflow.events
import controlflow.orchestration
import controlflow.tools
import dotenv
import langchain_openai
import uuid

from utils import TaskFactory

# Make sure you populate your .env file with the correct credentials!
dotenv.load_dotenv()

# Agent Catalog serves versioned tools and prompts.
# For a comprehensive list of what parameters can be set here, see the class documentation.
# Parameters can also be set with environment variables (e.g., bucket = $AGENT_CATALOG_BUCKET).
catalog = agentc.Catalog()

# By default, secrets defined in tools are pulled from the environment.
# For applications that require more complex secret management, you can define your secret values in the constructor.
# The 'keys' of this dictionary map to the values in various tool definitions (e.g., blogs_from_interests.yaml).
# The 'values' of this dictionary map to actual values required by the tool.
# catalog = agentc.Catalog(
#   secrets={
#       "CB_CONN_STRING": some_secrets_manager.get("CB_CONN_STRING"),
#       "CB_USERNAME": some_secrets_manager.get("CB_USERNAME"),
#       "CB_PASSWORD": some_secrets_manager.get("CB_PASSWORD"),
#       "CB_CERTIFICATE": some_secrets_manager.get("CB_CERTIFICATE"),
#   },
# )

# An Agent Catalog Span provides logging capabilities that will bind all LLM messages to...
# 1. a specific catalog snapshot (i.e., the version of the catalog when the agent was started), and
# 2. a specific span (as a log identifier).
# 3. any additional metadata (e.g., the_framework) that you want to associate with the conversation as kwargs.
span = catalog.Span(name="Starter Agent", the_framework="controlflow")
chat_model = langchain_openai.chat_models.ChatOpenAI(model_name="gpt-4o", temperature=0)


def run_flow(thread_id: str):
    # We want to group all events that occur during this conversation thread.
    # This is done by defining a nested span with a context manager.
    with span.new(name=f"Conversation {thread_id}") as scp:
        # We provide a LangChain specific decorator (agentc_langchain.audit) to inject this auditor into ChatModels.
        starter_agent = controlflow.Agent(
            name="Starter Agent",
            model=agentc_langchain.audit(chat_model, span=scp),
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
            scp.log(kind="assistant", content=message)
            if get_response:
                response = input(message)
                scp.log(kind="human", content=response)
                return response
            return "Message sent to user."

        # Below, we have a helper class that removes some of the boilerplate for using Agent Catalog + ControlFlow.
        task_factory = TaskFactory(
            span=scp,
            agent=starter_agent,
            tools=[talk_to_user],
        )

        # Write your agent logic (i.e., task graph) here!
        while True:
            find_source_and_dest = catalog.find("prompt", name="find_source_and_dest")
            endpoints = task_factory.run(find_source_and_dest)

            # We "draw" implicit dependency edges by using the results of previous tasks.
            # In this example all tasks are executed eagerly (though there is some limited support for lazy evaluation).
            find_travel_routes = catalog.find("prompt", name="find_travel_routes")
            travel_routes = task_factory.run(
                find_travel_routes,
                context={
                    "source_airport": endpoints["source_airport"],
                    "destination_airport": endpoints["dest_airport"],
                },
                result_type=str,
            )
            print(f"Your routes are: {travel_routes}")
            ask_to_continue = catalog.find("prompt", name="ask_to_continue")
            is_continue = task_factory.run(
                ask_to_continue,
                result_type=[True, False],
            )
            if not is_continue:
                break


if __name__ == "__main__":
    run_flow(thread_id=uuid.uuid4().hex)
