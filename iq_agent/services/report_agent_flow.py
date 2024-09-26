import controlflow
import controlflow.tools
import dotenv
import langchain_core.tools
import langchain_openai
import os
import pydantic
import queue
import agentc
import agentc.langchain
import typing

# Load our OPENAI_API_KEY.
dotenv.load_dotenv()


def run_flow(thread_id: str, to_user_queue: queue.Queue, from_user_queue: queue.Queue):
    # The agentc catalog provider serves versioned tools and prompts.
    # For a comprehensive list of what parameters can be set here, see the class documentation.
    # Parameters can also be set with environment variables (e.g., bucket = $agentc_BUCKET).
    provider = agentc.Provider(
        # This 'decorator' parameter tells us how tools should be returned (in this case, as a LangChain tool).
        decorator=langchain_core.tools.StructuredTool.from_function,
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

    def talk_to_user(message: str, get_response: bool = True) -> str:
        """
        Send a message to the human user and optionally wait for a response. If `get_response` is True, the function
        will return the user's response, otherwise it will return a simple confirmation. Do not send the user
        concurrent messages that require responses, as this will cause confusion.

        You may need to ask the human about multiple tasks at once. Consolidate your questions into a single message.
        For example, if Task 1 requires information X and Task 2 needs information Y, send a single message that
        naturally asks for both X and Y.
        """
        to_user_queue.join()
        to_user_queue.put(message)
        if get_response:
            response = from_user_queue.get()
            from_user_queue.task_done()
            return response
        return "Message sent to user."

    # The agentc LLM auditor will bind all LLM messages to...
    # 1. a specific agentc catalog snapshot (i.e., the version of the catalog when the agent was started), and
    # 2. a specific conversation thread / session (passed in via session=thread_id).
    # We provide a LangChain specific decorator (agentc.langchain.audit) to inject this auditor into ChatModels.
    # Note: similar to a agentc provider, the parameters of a agentc auditor can be set with environment variables.
    auditor = agentc.auditor.Auditor(llm_name="gpt-4o")
    chat_model = langchain_openai.chat_models.ChatOpenAI(model="gpt-4o", temperature=0.0)
    travel_agent = controlflow.Agent(
        name="Couchbase Travel Agent",
        model=agentc.langchain.audit(chat_model, session=thread_id, auditor=auditor),
    )
    with controlflow.Flow(agents=[travel_agent], thread_id=thread_id) as travel_flow:
        # Below, we have a helper function which will fetch the versioned prompts + tools from the catalog.
        def Task(prompt_name: str, **kwargs) -> controlflow.Task:
            with travel_flow:
                prompt: agentc.provider.Prompt = provider.get_prompt_for(name=prompt_name)
                if prompt is None:
                    raise RuntimeError(f"Prompt not found with the name {prompt_name}!")
                tools = prompt.tools + [talk_to_user] if prompt.tools is not None else [talk_to_user]
                return controlflow.Task(objective=prompt.prompt, tools=tools, **kwargs)

        while True:
            # Request router: find out what the user wants to do.
            get_user_intent = Task(
                prompt_name="get_user_intent",
                result_type=["United States data report", "United Kingdom data report"],
            )
            travel_flow.add_task(get_user_intent)
            travel_flow.run()

            # Decide the next task.
            data_analysis_type = get_user_intent.result

            match data_analysis_type:
                case "United States data report":
                    next_task = _build_data_analysis_task_US(Task)
                case "United Kingdom data report":
                    next_task = _build_data_analysis_task_UK(Task)
                case _:
                    raise RuntimeError("Bad response returned from agent!")

            travel_flow.run()
            if next_task.is_failed():
                Task(prompt_name="handle_failed_task")
                travel_flow.run()
                break

            # See if the user wants to continue.
            ask_to_continue = Task(
                prompt_name="ask_to_continue",
                result_type=[True, False],
            )
            travel_flow.add_task(ask_to_continue)
            travel_flow.run()
            if ask_to_continue.result is False:
                break

def _build_NL2SQL_task(Task: typing.Callable[..., controlflow.Task], collection: str, user_natural_language_query: str) -> controlflow.Task:
    print(os.getenv("CB_JWT_TOKEN"), "token")
    return Task(
        prompt_name="generate_sql_query_and_execute",
        context={
            "bucket": "travel-sample",
            "collection": collection,
            "scope": "inventory",
            "username": "Administrator", 
            "password": "password", 
            "cluster_url": "couchbase://127.0.0.1", 
            "jwt_token": os.getenv("CB_JWT_TOKEN"), 
            "capella_address": "https://api.dev.nonprod-project-avengers.com", 
            "org_id": "6af08c0a-8cab-4c1c-b257-b521575c16d0",
            "natural_language_query": user_natural_language_query}
    )


def _build_data_analysis_task_US(Task: typing.Callable[..., controlflow.Task]) -> controlflow.Task:
    # Task 1: Get the destination airport.
    top_10_hotels = _build_NL2SQL_task(Task, "hotel", "find the top 10 hotels in the United States order by decreasing order of number of public likes")
    top_10_routes = _build_NL2SQL_task(Task, "route", "find the top 10 routes in the United States order by decreasing order of number of schedules")

    

def _build_data_analysis_task_UK(Task: typing.Callable[..., controlflow.Task]) -> controlflow.Task:
    # Task 1: Get the destination airport.
    top_10_hotels = _build_NL2SQL_task(Task, "hotel", "find the top 10 hotels in the United kingdom order by decreasing order of number of public likes")
    top_10_routes = _build_NL2SQL_task(Task, "route", "find the top 10 routes in the United kingdom order by decreasing order of number of schedules")

    