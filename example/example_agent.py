import rosetta.lc
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

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

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
cluster = Cluster('couchbase://10.100.172.95', ClusterOptions(auth))

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
    print("\nUpsert CAS: ")
    try:
        # key will equal: "airline_8091"
        key = doc["type"] + "_" + str(doc["id"])
        result = cb_coll.upsert(key, doc)
        print(result)
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

def gen_doc(id: str, name: str, callsign: str):
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
    if"tool_calls" in content["choices"][0]["message"]:
                print(content["choices"][0]["message"]["tool_calls"][0]["function"])
                
                func = globals()[content["choices"][0]["message"]["tool_calls"][0]["function"]["name"]]

                print(func)

                if content["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "gen_doc":

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

test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))
test.setFields()

s1 = test.invoke([
    SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
    HumanMessage(content="Can you gen a doc with ID=8091, callsign=CBA, and name=Couchbase Airways"),
])
tools = [upsert_document, gen_doc, get_airline_by_key]

testWithTools = test.bind_tools(tools)

s2 = test.invoke([
    SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
    HumanMessage(content="Can you gen a doc with ID=8091, callsign=CBA, and name=Couchbase Airways"),
])

print("Without Binding: ", s1)
print()
print("With Binding: ", s2)

content = json.loads(s2.content)

for x in content:
    print(f"{x}: {content[x]}")

print()

processResponse()

print(storedAirlines)

content = json.loads(test.invoke([HumanMessage(content="Can you upsert the doc you just generated")]).content)

print()

processResponse()