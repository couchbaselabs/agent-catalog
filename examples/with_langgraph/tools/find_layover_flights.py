import agentc
import couchbase.auth
import couchbase.cluster
import couchbase.options
import dotenv
import os
import pydantic

dotenv.load_dotenv()

# Agent Catalog imports this file once (even if both tools are requested).
# To share (and reuse) Couchbase connections, we can use a global variable.
cluster = couchbase.cluster.Cluster(
    os.getenv("CB_CONN_STRING"),
    couchbase.options.ClusterOptions(
        authenticator=couchbase.auth.PasswordAuthenticator(
            username=os.getenv("CB_USERNAME"), password=os.getenv("CB_PASSWORD")
        )
    ),
)


# Define a Pydantic model to provide more information to the LLM when analyzing a tool's output.
class Route(pydantic.BaseModel):
    airlines: list[str]
    layovers: list[str]
    from_airport: str
    to_airport: str


@agentc.catalog.tool
def find_one_layover_flights(source_airport: str, destination_airport: str) -> list[Route]:
    """Find all one-layover (indirect) flights between two airports."""
    query = cluster.query(
        """
            FROM
                `travel-sample`.inventory.route r1,
                `travel-sample`.inventory.route r2
            WHERE
                r1.sourceairport = $source_airport AND
                r1.destinationairport = r2.sourceairport AND
                r2.destinationairport = $destination_airport
            SELECT VALUE {
                "airlines"     : [r1.airline, r2.airline],
                "layovers"     : [r1.destinationairport],
                "from_airport" : r1.sourceairport,
                "to_airport"   : r2.destinationairport
            }
            LIMIT
                10;
        """,
        couchbase.options.QueryOptions(
            named_parameters={"source_airport": source_airport, "destination_airport": destination_airport}
        ),
    )
    results: list[Route] = list()
    for result in query.rows():
        results.append(Route(**result))
    return results


@agentc.catalog.tool
def find_two_layover_flights(source_airport: str, destination_airport: str) -> list[Route]:
    """Find all two-layover (indirect) flights between two airports."""
    query = cluster.query(
        """
            FROM
                `travel-sample`.inventory.route r1,
                `travel-sample`.inventory.route r2,
                `travel-sample`.inventory.route r3
            WHERE
                r1.sourceairport = $source_airport AND
                r1.destinationairport = r2.sourceairport AND
                r2.destinationairport = r3.sourceairport AND
                r3.destinationairport = $destination_airport
            SELECT VALUE {
                "airlines"     : [r1.airline, r2.airline, r3.airline],
                "layovers"     : [r1.destinationairport],
                "from_airport" : r1.sourceairport,
                "to_airport"   : r3.destinationairport
            }
            LIMIT
                10;
        """,
        couchbase.options.QueryOptions(
            named_parameters={"source_airport": source_airport, "destination_airport": destination_airport}
        ),
    )
    results: list[Route] = list()
    for result in query.rows():
        results.append(Route(**result))
    return results
