"""
User needs to add user parameters in .env file
"""

import rosetta_lc
import json
import os
from datetime import timedelta 
# needed for any cluster connection
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
# needed for options -- cluster, timeout, SQL++ (N1QL) query, etc.
from couchbase.options import (ClusterOptions, ClusterTimeoutOptions,
                               QueryOptions)
#Get all docs in a range
from couchbase.kv_range_scan import RangeScan

from dotenv import load_dotenv, dotenv_values 
load_dotenv()

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain_core.utils.function_calling import convert_to_openai_tool

#Imports Fine in Virtual Environment

# Update this to your cluster
username = "Administrator"
password = "password"
bucket_name = "travel-sample"
# User Input ends here.

# Connect options - authentication
auth = PasswordAuthenticator(
    username,
    password,
)

# Get a reference to our cluster
# NOTE: For TLS/SSL connection use 'couchbases://<your-ip-address>' instead
cluster = Cluster(os.getenv("CONN_STRING"), ClusterOptions(auth))

# Wait until the cluster is ready for use.
cluster.wait_until_ready(timedelta(seconds=5))

# get a reference to our bucket
cb = cluster.bucket(bucket_name)

cb_coll = cb.scope("inventory").collection("airline")

storedAirlines = []

def upsert_document(doc):
    """
    Upsert a document into the cluster
    """
    print(f"upserting: {doc}")
    print("\nUpsert CAS: ")
    try:
        key = doc["type"] + "_" + str(doc["id"])
        result = cb_coll.upsert(key, doc)
        print(result.cas)
    except Exception as e:
        print(e)

# get document function
def get_airline_by_key(key):
    """
    Given a key in the format 'airline_XXXX', retrieve the airline with that key from the cluster.
    """
    print("\nGet Result: ")
    try:
        result = cb_coll.get(key)
        print(result.content_as[str])
    except Exception as e:
        print(e)

def gen_doc(id: int, name: str, callsign: str):
    """
    Generates a doc with the given id, name and callsign, and returns it.
    """
    try:
        airline = {
            "type": "airline",
            "id": id,
            "iata": None,
            "icao": None,
            "callsign": callsign,
            "name": name,
        }  
        print("Generated doc: ", airline)
        return airline   
    except Exception as e:
        print("Generate failed.")
        print("Exception: ", e)

content = {}

def processResponse():
    if "tool_calls" in content["choices"][0]["message"]:
        print(content["choices"][0]["message"]["tool_calls"][0]["function"])
        
        func = globals()[content["choices"][0]["message"]["tool_calls"][0]["function"]["name"]]

        if content["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "gen_doc":

            argsDict = json.loads(content["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
            print(content["choices"][0]["message"]["tool_calls"][0]["function"]["name"])
            s2 = func(argsDict["id"], argsDict["name"], argsDict["callsign"])
            storedAirlines.append(s2)
        
        elif content["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "upsert_document":
            if storedAirlines:
                print(storedAirlines[0])
                func(storedAirlines[0])
                storedAirlines.pop(0)

        elif content["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_airline_by_key":
            argsDict = json.loads(content["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
            func(argsDict["key"])

    else: 
        for x in content:
            print(f"{x}: {content[x]}")


test = rosetta_lc.IQBackedChatModel(model_name="custam",capella_address=os.getenv("CAPELLA-ADDRESS"), org_id=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))


def example1():

    s1 = test.invoke([
        SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster."),
        HumanMessage(content="Can you gen a doc with ID=8091, callsign=CBA, and name=Couchbase Airways"),
    ])

    tools = [upsert_document, gen_doc, get_airline_by_key]
    test.bind_tools(tools)

    s2 = test.invoke([
        SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
        HumanMessage(content="Can you gen a doc with ID=8091, callsign=CBA, and name=Couchbase Airways"),
    ])

    print(f"To Invoke:\nSystemMessage = You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. \nHumanMessage = Can you gen a doc with ID=8091, callsign=CBA, and name=Couchbase Airways")

    print(f"Without Binding:\n")
    content1 = json.loads(s1.content)

    for x in content1:
        print(f"{x}: {content1[x]}")

    print()
    print(f"With Binding:\n")

    content2 = json.loads(s2.content)

    for x in content2:
        print(f"{x}: {content2[x]}")


    print()

    processResponse()

    print(storedAirlines)

    content = json.loads(test.invoke([HumanMessage(content="Can you upsert the doc you just generated")]).content)

    print()

    processResponse()

def example2():

    inp = input("Input (q to exit): ")

    while inp.lower() != "q":
        resp = test.invoke([
            SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. Make sure you clarify on accepted arguments."),
            HumanMessage(content=inp),
        ])

        content = json.loads(resp.content)
        processResponse()
        print
        inp = input("Input (q to exit): ")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a very powerful assistant, with knowledge about Couchbase Server and Clusters."
            ),
            (
                "user",
                "{input}"
            ),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ]
    )

    agent = (
        {
            "input": lambda x: x["input"],
            "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                x["intermediate_steps"]
            ),
        }
        | prompt
        | test
        | OpenAIToolsAgentOutputParser()
        )
    agent_executor = AgentExecutor(agent=agent, tools=[], verbose=True)


    agent_executor.invoke({"input": "Can you genetate and upsert a document with the details of id=312, callsign=CBA, and name=Couchbase Airways"})"""