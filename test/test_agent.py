import pytest
import rosetta.lc
import random
import pydantic
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

#Tests with invalid parameters for IQAgent
def test_par1():
    with pytest.raises(pydantic.v1.error_wrappers.ValidationError) as excinfo:
        test = rosetta.lc.IQAgent() 

def test_par2():
    with pytest.raises(pydantic.v1.error_wrappers.ValidationError) as excinfo:
        test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username="Daniel")

def test_par3():
    with pytest.raises(pydantic.v1.error_wrappers.ValidationError) as excinfo:
        test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), password="12345")

def test_par4():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

#Tests with tools for IQAgent
def test_tools1():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))
    test.bind_tools([upsert_document, gen_doc, get_airline_by_key])
    s = test.invoke([
    SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
    HumanMessage(content="Can you gen a doc with ID=8091, callsign=CBA, and name=Couchbase Airways"),
    ])
    print(s)

def test_tools2():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))
    
    test.bind_tools([1, 2, 3]) #Wow works w/ convert_to_openai_tool

#Tests with setting functions
def test_set1():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

    test.select_settings(temperature=1.5, seed=random.randint(1,10000), freq_penalty=1, presence_penalty=-1)
    print(test.invoke([
        SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
        HumanMessage(content="Can you tell me how to use SQL to access data in the Couchbase Server Cluster.")
    ]))

def test_set2():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

    with pytest.raises(ValueError) as excinfo:
        test.select_settings(freq_penalty=3)

def test_set3():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))
    
    test.select_model(4)
    print(test.invoke([
        SystemMessage(content="You are a helpful assistant who knows everything, especially about the Couchbase Server Cluster. "),
        HumanMessage(content="Can you tell me about the solor system?")        
    ]))

    test.select_model("gpt-4o-mini")
    print(test.invoke([
        HumanMessage(content="Can you tell me about the solor system?")        
    ]))

def test_set4():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))
    
    with pytest.raises(ValueError) as excinfo:
        test.select_model(5)

def test_set5():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

    with pytest.raises(ValueError) as excinfo:
        test.select_model("Couchbase")

#Tests with generation/streaming
def test_gen1():
    test = rosetta.lc.IQAgent(model_name="custam",capAddy=os.getenv("CAPELLA-ADDRESS"), orgID=os.getenv("ORG-ID"), username=os.getenv("USERNAME"), password=os.getenv("PASSWORD"))

def test_stream1():
    pass