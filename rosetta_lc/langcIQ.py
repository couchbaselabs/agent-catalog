from typing import Any, Dict, Iterator, List, Optional, Callable, Dict, Sequence, Type, Union
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_core.language_models import BaseChatModel
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.tools import BaseTool
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain.agents import tool
from joblib import Memory
import requests
import subprocess
import json
import logging
import time
import os
from dotenv import load_dotenv, dotenv_values 
load_dotenv()
logging.root.setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)
class CustomChatModel(BaseChatModel):
    """
    Custom Chat Model that calls IQ proxy
    """

    model_name: str
    """The name of the model"""

    capAddy: str
    """Base URL for capella IQ """

    orgID: str
    """Org ID for capella IQ"""

    hJWT: str
    """JWT token"""

    _supportedModels = [
        "gpt-4",
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ]

    _payload = {
        "messages": [],
        "completionSettings": {
            "model": _supportedModels[0],
            "stream": False,
            "type": "json_object",
        }
    }
    """Payload for iq-proxy request"""

    _payloadOld = {
        "messages": [], 
        "completionSettings": {
            "model":"gpt-4", 
            "stream": False,
            "type": "json_object",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "gen_doc",
                        "description": "Generates a document for an airline and returns it.", 
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "id" : {"type": "string", "description": "the id of the airline"},
                                "name": {"type": "string", "description": "the name of the airline"},
                                "callsign": {"type": "string", "description": "the callsign of the airline"}
                            },
                            "required": ["id", "name", "callsign"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function":{
                        "name": "get_airline_by_key",
                        "descrition": "Retrieves an airline with a given key",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string", "description": "the key of the airline to retrieve, in the form of airline_xxxx"}
                            },
                            "required": ["key"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "upsert_document",
                        "description": "Updates/Inserts a document into a collection",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "doc": {"type": "object", "description": "the document to be inserted into the collection"},
                            },
                            "required": ["doc"]
                        }

                    }
                }
            ]
        },

    }

    """def getTools(self):
        return [upsert_document, gen_doc, get_airline_by_key]"""

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    )    -> ChatResult: 
        """Override the _generate method to implement the chat model logic.

        This can be a call to an API, a call to a local model, or any other
        implementation that generates a response to the input prompt.

        Args:
            messages: the prompt composed of a list of messages.
            stop: a list of strings on which the model should stop generating.
                  If generation stops due to a stop token, the stop token itself
                  SHOULD BE INCLUDED as part of the output. This is not enforced
                  across models right now, but it's a good practice to follow since
                  it makes it much easier to parse the output of the model
                  downstream and understand why generation stopped.
            run_manager: A run manager with callbacks for the LLM. 
        """

        # Seperate inputs into system or human messages, could add more for other types
        for x in messages:
            if x.type == "system":
                self._payload["messages"].append(
                    {"role": "system",
                     "content": x.content}
                )
            elif x.type == "human":
                self._payload["messages"].append(
                    {"role": "user",
                     "content": x.content}
                )
        
        # _generate is one-time invoke, so no stream
        self._payload["completionSettings"]["stream"] = False

        urlCompletion = self.capAddy + "/v2/organizations/" + self.orgID + "/integrations/iq/openai/chat/completions"
        h = {
                'Content-Type': 'application/json',
                "Authorization": self.hJWT
        }

        #Send request to IQ-Proxy
        try:

            r = requests.post(urlCompletion, json=self._payload, headers=h)

            r2 = AIMessage(
                content=r.text,
                additional_kwargs={},  # Used to add additional payload (e.g., function calling request)
                response_metadata={},  # Use for response metadata 
            )

            generation = ChatGeneration(message=r2)
            return ChatResult(generations=[generation])       
        except:
            logger.error("Error in requesting to IQ-proxy")
    
    def _stream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        """
        Stream the output of the model.

        This method should be implemented if the model can generate output
        in a streaming fashion. If the model does not support streaming,
        do not implement it. In that case streaming requests will be automatically
        handled by the _generate method.

        Args:
            messages: the prompt composed of a list of messages.
            stop: a list of strings on which the model should stop generating.
                    If generation stops due to a stop token, the stop token itself
                    SHOULD BE INCLUDED as part of the output. This is not enforced
                    across models right now, but it's a good practice to follow since
                    it makes it much easier to parse the output of the model
                    downstream and understand why generation stopped.
            run_manager: A run manager with callbacks for the LLM.
        """

        self._payload["completionSettings"]["stream"] = True

        urlCompletion = self.capAddy + "/v2/organizations/" + self.orgID + "/integrations/iq/openai/chat/completions"
        h = {
                'Content-Type': 'application/json',
                "Authorization": self.hJWT
        }

        for x in messages:
            if x.type == "system":
                self._payload["messages"].append(
                    {"role": "system",
                     "content": x.content}
                )
            elif x.type == "human":
                self._payload["messages"].append(
                    {"role": "user",
                     "content": x.content}
                )

        try:
            r = requests.post(urlCompletion, json=self._payload, headers=h, stream=True)

            for token in r.text:
                chunk = ChatGenerationChunk(message=AIMessageChunk(content=token))
                yield chunk
        except:
            logger.error("Error in streaming response")
    
    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], Type[BaseModel], Callable, BaseTool]],
        **kwargs: Any,
    ):
        """
        Binds tools to the model. 

        Args: 
            tools: List of tools to add to LLM. 
        """

        #convert_to_openai_tool to convert funcs to dict for passing through payload
        try:
            for x in tools:
                y = convert_to_openai_tool(x)
                if "tools" not in self._payload["completionSettings"]:
                    self._payload["completionSettings"]["tools"] = [y]
                else:
                    self._payload["completionSettings"]["tools"].append(y)
        except:
            logging.error("Error in binding tools")

    def select_model(
        self,
        modelName: Optional[str],
        modelNum: Optional[int]
    ):
        """
        Selects a model to use for the agent.

        Args:
            modelName: name of model to select
            modelNum: number of model to select based on field
        """
        try: 
            if modelName and modelName in self._supportedModels:
                self._payload["completionSettings"]["model"] = modelName
            elif modelNum and modelNum < len(self._supportedModels):
                self._payload["completionSettings"]["model"] = self._supportedModels[modelNum]
            else:
                raise ValueError("Invalid model.")

        except:
            logging.error("Error in selecting model")
    
    def select_settings(
        self,
        temperature: Optional[float],
        seed: Optional[int],
        presence_penalty: Optional[float],
        freq_penalty: Optional[float]
    ):
        """
        Select certain settings for tuning on chat completions.

        Args:
            temperature: Between 0 and 2, where higher values make response more random, and lower values make it more focused
            seed: samples deterministically based on given seed
            presence_penalty: Between -2 and 2, positive values penalize new tokens based on if they appear, increasing likelihood to talk about new topics
            freq_penalty: Between -2 and 2, positive values penalize new tokens based on their existing frequency, decreasing likelihood to repeat the same line 
        """
        try:
            temperature_check = temperature >= 0 and temperature <= 2
            presence_penalty_check = presence_penalty >= -2 and presence_penalty <= 2
            freq_penalty_check = freq_penalty >= -2 and freq_penalty <= 2

            if temperature and temperature_check: 
                self._payload["completionSettings"]["temperature"] = temperature

            if seed:
                self._payload["completionSettings"]["seed"] = seed

            if presence_penalty and presence_penalty_check:
                self._payload["completionSettings"]["presence_penalty"] = presence_penalty

            if freq_penalty and freq_penalty_check:
                self._payload["completionSettings"]["frequency_penalty"] = freq_penalty

            if (temperature and not temperature_check) or (presence_penalty and not presence_penalty_check) or (freq_penalty and not freq_penalty_check):
                raise ValueError("Error in temp/pres/freq for settings")
                
        except:
            logging.error("Error in selecting settings.")

    @property
    def _llm_type(self) -> str:
        return "iq-proxy"
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        """Return a dictionary of identifying parameters.

        This information is used by the LangChain callback system, which
        is used for tracing purposes make it possible to monitor LLMs.
        """
        return {
            # The model name allows users to specify custom token counting
            # rules in LLM monitoring applications (e.g., in LangSmith users
            # can provide per token pricing for their model and monitor
            # costs for the given LLM.)
            "model_name": self.model_name,
        }
 
memory = Memory("cachedir")

if __name__ == "__main__":

    JWT = subprocess.run("./../genJWT.sh", capture_output=True, text=True).stdout.strip()
    toInserthJWT = "Bearer " + JWT

    model = CustomChatModel(model_name="my_custom_model", capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), hJWT=toInserthJWT)


    #@memory.cache dont want cacheing when 
    def invoker(s):
        returnS = model.invoke(
            [
                #HumanMessage(content="hello!"),
                SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
                HumanMessage(content=s),
            ]
        )
        return returnS

    while True:

        inp = input("Request (q to end): ")
        if inp.lower() == "q":
            break

        sT = time.time()
        s = invoker(inp)
        eT = time.time()
        logger.info(f"Time: {eT-sT}")      
        content = json.loads(s.content)

        """if skip and "tool_calls" in content["choices"][0]["message"]:
            print(content["choices"][0]["message"]["tool_calls"][0]["function"])
            
            func = globals()[content["choices"][0]["message"]["tool_calls"][0]["function"]["name"]]

            print(func)

            if cont ent["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "gen_doc":

                argsDict = json.loads(content["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
                print(content["choices"][0]["message"]["tool_calls"][0]["function"]["name"])
                s2 = func(argsDict["id"], argsDict["name"], argsDict["callsign"])
                storedAirlines.append(s2)
            
            elif content["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "upsert_document":
                if storedAirlines:
                    func(storedAirlines[0])
                    storedAirlines.pop(0)

            elif content["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_airline_by_key":
                argsDict = json.loads(content["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
                func(argsDict["key"])

        else:"""
        for x in content:
            logging.warning(f"\t{x}: {content[x]}") 