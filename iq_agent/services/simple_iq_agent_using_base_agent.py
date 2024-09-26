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

from base_agent import BaseAgentUsingagentc
# Load our OPENAI_API_KEY.

class SimpleIQAgent(BaseAgentUsingagentc):
    def __init__(self):
        super().__init__(model_name = "gpt-4o")


    def execute_flow(self, thread_id: str, to_user_queue: queue.Queue, from_user_queue: queue.Queue, *args, **kwargs):
        travel_agent = controlflow.Agent(
            name="Couchbase Travel Agent",
            model=agentc.langchain.audit(self.chat_model, session=thread_id, auditor=self.auditor),
        )
        with controlflow.Flow(agents=[travel_agent], thread_id=thread_id) as travel_flow:
            # Below, we have a helper function which will fetch the versioned prompts + tools from the catalog.

            while True:

                get_user_intent_task = self._get_user_intent_task(travel_agent)
                # Request router: find out what the user wants to do.
                print(1)
                travel_flow.add_task(get_user_intent_task)
                travel_flow.run()

                # Decide the next task.
                user_natural_language_query = get_user_intent_task.result
                print(user_natural_language_query)
                next_task = self._build_NL2SQL_task(travel_agent, user_natural_language_query)
                travel_flow.run()
                if next_task.is_failed():
                    self._get_handle_failed_task(travel_agent)
                    travel_flow.run()
                    break

                # See if the user wants to continue.
                ask_to_continue_task = self._get_ask_to_continue_task(travel_agent)
                travel_flow.add_task(ask_to_continue_task)
                travel_flow.run()
                if ask_to_continue_task.result is False:
                    break


    def _build_NL2SQL_task(self, control_flow_agent, user_natural_language_query: str) -> controlflow.Task:
        return self.create_task_using_agentc(
            control_flow_agent,
            prompt_name="generate_sql_query_and_execute",
            context={
                "bucket": "travel-sample",
                "collection": "airport",
                "scope": "inventory",
                "username": "Administrator", 
                "password": "password", 
                "cluster_url": "couchbase://127.0.0.1", 
                "jwt_token": os.getenv("CB_JWT_TOKEN"), 
                "capella_address": "https://api.dev.nonprod-project-avengers.com", 
                "org_id": "6af08c0a-8cab-4c1c-b257-b521575c16d0",
                "natural_language_query": user_natural_language_query}
        )