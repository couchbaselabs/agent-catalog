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
import inspect

# Load our OPENAI_API_KEY.
dotenv.load_dotenv()

class BaseAgentUsingagentc:
    def __init__(self, model_name):
        # The agentc catalog provider serves versioned tools and prompts.
        # For a comprehensive list of what parameters can be set here, see the class documentation.
        # Parameters can also be set with environment variables (e.g., bucket = $agentc_BUCKET).
        self.provider = agentc.Provider(
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
        self.auditor = agentc.auditor.Auditor(llm_name=model_name)
        self.chat_model = langchain_openai.chat_models.ChatOpenAI(model=model_name, temperature=0.0)

    @staticmethod
    def talk_to_user(to_user_queue, from_user_queue, message: str, get_response: bool = True) -> str:
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

    def create_task_using_agentc(self, control_flow_agent, prompt_name: str, **kwargs) -> controlflow.Task:
        with control_flow_agent:
            prompt: agentc.provider.Prompt = self.provider.get_prompt_for(name=prompt_name)
            if prompt is None:
                raise RuntimeError(f"Prompt not found with the name {prompt_name}!")
            tools = prompt.tools + [self.talk_to_user] if prompt.tools is not None else [self.talk_to_user]
            return controlflow.Task(objective=prompt.prompt, tools=tools, **kwargs)

    def _get_ask_to_continue_task(self, control_flow_agent):
        return self.create_task_using_agentc(
            control_flow_agent,
            prompt_name="ask_to_continue",
            result_type=[True, False],
        )

    def _get_handle_failed_task(self, control_flow_agent):
        return self.create_task_using_agentc(control_flow_agent, prompt_name="handle_failed_task")


    def _get_user_intent_task(self, control_flow_agent):
        return self.create_task_using_agentc(
            control_flow_agent,
            prompt_name="get_user_intent",
            result_type=str,
        )

    
    def execute_flow(self, thread_id: str, to_user_queue: queue.Queue, from_user_queue: queue.Queue, *args, **kwargs):
        pass
