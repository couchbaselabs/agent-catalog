import agent_catalog_lc
import couchbase.auth
import couchbase.cluster
import couchbase.exceptions
import couchbase.options
import datetime
import dotenv
import langchain.agents
import langchain.prompts
import langchain_core.tools
import os
import typing

# Load our environment variables.
dotenv.load_dotenv()

# Connect to our Couchbase instance. This could be different from your Capella instance.
cluster = couchbase.cluster.Cluster(
    os.getenv("CB_CONN_STRING"),
    couchbase.options.ClusterOptions(
        couchbase.auth.PasswordAuthenticator(
            username=os.getenv("CB_USERNAME"),
            password=os.getenv("CB_PASSWORD"),
        )
    ),
)
cluster.wait_until_ready(datetime.timedelta(seconds=5))
bucket = cluster.bucket(os.getenv("CB_BUCKET"))
collection = bucket.scope("inventory").collection("airline")


@langchain_core.tools.tool
def add_airline_document(airline_document: typing.Dict) -> bool:
    """Insert or update an airline JSON document."""
    print(f"Adding the following doc: {airline_document}")
    key = airline_document["type"] + "_" + str(airline_document["id"])
    result = collection.upsert(key, airline_document)
    if result.success:
        print("Document successfully added.")
        return True

    print("Document was not added successfully.")
    return False


@langchain_core.tools.tool
def get_airline_document(airline_key: str) -> typing.Dict | None:
    """Given a key in the format 'airline_XXXX', retrieve an airline JSON document."""
    print(f"Looking for the document with the following key: {airline_key}")
    try:
        result = collection.get(airline_key)
        result_as_dict = result.content_as[dict]
        print(f"Found document with key {airline_key}: {result_as_dict}")
        return result_as_dict

    except couchbase.exceptions.DocumentNotFoundException:
        print(f"Document with key {airline_key} not found.")
        return None


@langchain_core.tools.tool
def assemble_airline_document(document_id: int, airline_name: str, callsign: str) -> typing.Dict:
    """Generate an airline JSON document with the given identifier, name and callsign."""
    airline = {
        "type": "airline",
        "id": document_id,
        "iata": None,
        "icao": None,
        "callsign": callsign,
        "name": airline_name,
    }
    print(f"Generated airline document: {airline}")
    return airline


if __name__ == "__main__":
    chat_model = agent_catalog_lc.models.IQBackedChatModel(
        model_name="gpt-4o",
        capella_address=os.getenv("CAPELLA_ADDRESS"),
        organization_id=os.getenv("CAPELLA_ORG_ID"),
        username=os.getenv("CAPELLA_USERNAME"),
        password=os.getenv("CAPELLA_PASSWORD"),
    )
    tools = [add_airline_document, get_airline_document, assemble_airline_document]
    prompt_template = langchain.prompts.ChatPromptTemplate(
        [
            ("system", "You are a helpful assistant who manages a database of airline documents."),
            ("placeholder", "{chat_history}"),
            ("human", "{user_input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )
    agent = langchain.agents.create_tool_calling_agent(chat_model, tools, prompt_template)
    executor = langchain.agents.AgentExecutor(agent=agent, tools=tools, verbose=True)
    invocation = executor.invoke(
        {"user_input": "Please add a new airline document with the ID=8091, callsign=CBA, and name=Couchbase Airways."}
    )
