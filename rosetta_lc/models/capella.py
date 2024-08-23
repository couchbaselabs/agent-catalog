import base64
import http
import logging
import openai.types
import requests
import typing

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.messages import AIMessageChunk
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration
from langchain_core.outputs import ChatGenerationChunk
from langchain_core.outputs import ChatResult
from langchain_core.pydantic_v1 import BaseModel
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic.v1 import HttpUrl
from pydantic.v1 import PrivateAttr
from pydantic.v1 import root_validator
from pydantic.v1 import validator

logger = logging.getLogger(__name__)

# TODO (GLENN): Use pathlib here instead?
CAPELLA_URL_SESSIONS_SUBDIRECTORY = "/sessions"
CAPELLA_URL_ORGANIZATIONS_SUBDIRECTORIES = "/v2/organizations/"
CAPELLA_URL_IQ_COMPLETIONS_SUBDIRECTORIES = "/integrations/iq/openai/chat/completions"


class IQBackedChatModel(BaseChatModel):
    """A Chat Model that calls IQ proxy for all completions."""

    model_name: openai.types.ChatModel = ...
    """ The name of the OpenAI model to use. """

    capella_address: HttpUrl = ...
    """ Base URL for your Capella instance. For example, https://api.cloud.couchbase.com. """

    organization_id: str = ...
    """ Organization ID associated with your Capella instance. """

    web_token: typing.Optional[str]
    """ JWT (web token) obtained by authenticating with $CAPELLA_ADDRESS/sessions.

    This field is optional, but if web_token is not specified then username and password are mandatory.
    """

    username: typing.Optional[str]
    """ Username associated with your Capella instance. Used to generate a JWT. """

    password: typing.Optional[str]
    """ Password associated with your Capella instance. Used to generate a JWT. """

    temperature: typing.Optional[float] = 0.0
    """ Temperature used for LLM completions. Must be between 0 and 2. Higher values = more random. """

    seed: typing.Optional[int] = None
    """ Seed used for LLM completions. """

    presence_penalty: typing.Optional[float] = None
    """ Penalty for "presence" used for LLM completions.

    This value must be between -2 and 2. Higher values = more likely to "talk" about new topics.
    """

    frequency_penalty: typing.Optional[float] = None
    """ Penalty for "frequency" used for LLM completions.

    This value must be between -2 and 2. Higher values = less likely to repeat the same line.
    """

    _tools: typing.List[typing.Dict[str, typing.Any]] = PrivateAttr(default_factory=list)

    @validator("temperature")
    @classmethod
    def temperature_must_be_between_0_and_2(cls, value):
        if not (0 < value < 2):
            raise ValueError("Invalid temperature! Must be between 0 and 2.")

    @validator("presence_penalty", "frequency_penalty")
    @classmethod
    def penalty_must_be_between_n2_and_2(cls, value):
        if not (-2 < value < 2):
            raise ValueError("Invalid penalty! Must be between -2 and 2.")

    @root_validator
    @classmethod
    def generate_web_token_if_necessary(cls, values):
        if values.get("web_token") is not None:
            return values

        if values.get("web_token") is None and (values.get("username") is None or values.get("password") is None):
            raise ValueError("web_token OR <username, password> must be specified!")
        auth = base64.b64encode(f'{values.get("username")}:{values.get("password")}'.encode("ascii"))
        auth_response = requests.post(
            values.get("capella_address") + CAPELLA_URL_SESSIONS_SUBDIRECTORY,
            headers={"Authorization": f"Basic {auth.decode('ascii')}"},
        )

        # Check the status code.
        if auth_response.status_code != http.HTTPStatus.OK:
            raise ValueError("Could not authenticate with Capella: " + auth_response.text)
        response_json = auth_response.json()

        # Make sure JWT is in our response.
        if "jwt" not in response_json:
            raise ValueError("Could not authenticate with Capella: " + auth_response.text)
        values["web_token"] = response_json["jwt"]

        logger.info("Authenticated with Capella using username and password.")
        return values

    def generate_payload(self) -> typing.Dict:
        payload = {
            "messages": list(),
            "completionSettings": {
                "model": self.model_name,
                "type": "json_object",
                # TODO (GLENN): There might be a bug on the Capella side? Casting this to an int.
                "temperature": int(self.temperature),
            },
        }
        completion_settings = payload["completionSettings"]
        if len(self._tools) > 0:
            completion_settings["tools"] = self._tools
        if self.seed is not None:
            completion_settings["seed"] = self.seed
        if self.presence_penalty is not None:
            completion_settings["presence_penalty"] = self.presence_penalty
        if self.frequency_penalty is not None:
            completion_settings["frequency_penalty"] = self.frequency_penalty
        return payload

    # TODO (KUSH): Implement stop and run_manager.
    def _generate(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> ChatResult:
        payload = self.generate_payload()

        # TODO (KUSH): Maybe add support for more types later on?
        # Separate inputs into system or human messages.
        for x in messages:
            if x.type == "system":
                payload["messages"].append({"role": "system", "content": x.content})
            elif x.type == "human":
                payload["messages"].append({"role": "user", "content": x.content})

        # _generate does not require us to stream.
        payload["completionSettings"]["stream"] = False

        # Send a completions request to IQ.
        completions_url = (
            self.capella_address
            + CAPELLA_URL_ORGANIZATIONS_SUBDIRECTORIES
            + self.organization_id
            + CAPELLA_URL_IQ_COMPLETIONS_SUBDIRECTORIES
        )
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.web_token}"}
        logger.debug(f"Issuing request {payload} to Capella IQ.")
        response = requests.post(completions_url, json=payload, headers=headers)
        if response.status_code != http.HTTPStatus.OK:
            raise RuntimeError("Non-OK status returned from Capella: " + response.text)

        message = AIMessage(
            content=response.text,
            # TODO (GLENN): Should there be anything here?
            additional_kwargs={},
            response_metadata={},
        )
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])

    # TODO (KUSH): Implement stop and run_manager.
    def _stream(
        self,
        messages: typing.List[BaseMessage],
        stop: typing.Optional[typing.List[str]] = None,
        run_manager: typing.Optional[CallbackManagerForLLMRun] = None,
        **kwargs: typing.Any,
    ) -> typing.Iterator[ChatGenerationChunk]:
        payload = self.generate_payload()
        payload["completionSettings"]["stream"] = True

        # TODO (KUSH): Maybe add support for more types later on?
        # Separate inputs into system or human messages.
        for x in messages:
            if x.type == "system":
                payload["messages"].append({"role": "system", "content": x.content})
            elif x.type == "human":
                payload["messages"].append({"role": "user", "content": x.content})

        # Send a completions request to IQ.
        completions_url = (
            self.capella_address
            + CAPELLA_URL_ORGANIZATIONS_SUBDIRECTORIES
            + self.organization_id
            + CAPELLA_URL_IQ_COMPLETIONS_SUBDIRECTORIES
        )
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.web_token}"}
        logger.debug(f"Issuing request {payload} to Capella IQ.")
        response = requests.post(completions_url, json=payload, headers=headers, stream=True)
        if response.status_code != http.HTTPStatus.OK:
            raise RuntimeError("Non-OK status returned from Capella: " + response.text)
        for token in response.text:
            yield ChatGenerationChunk(message=AIMessageChunk(content=token))

    def bind_tools(
        self,
        tools: typing.Sequence[
            typing.Union[typing.Dict[str, typing.Any], typing.Type[BaseModel], typing.Callable, BaseTool]
        ],
        **kwargs: typing.Any,
    ):
        # Convert_to_openai_tool to convert funcs to dict for passing through payload.
        try:
            for x in tools:
                tool = convert_to_openai_tool(x)
                self._tools.append(tool)
            return self

        except Exception as e:
            logging.error(f"Encountered error while trying to convert tool to OpenAI tool: {str(e)}")
            raise e

    @property
    def _llm_type(self) -> str:
        return "iq-proxy"

    @property
    def _identifying_params(self) -> typing.Dict[str, typing.Any]:
        """Return a dictionary of identifying parameters.

        Note: This information is used by the LangChain callback system, which is used for tracing purposes make it
        possible to monitor LLMs.
        """
        return {
            "model_name": self.model_name,
        }
