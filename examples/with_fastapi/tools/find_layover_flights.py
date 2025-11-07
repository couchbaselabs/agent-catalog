import agentc
import couchbase.auth
import couchbase.cluster
import couchbase.exceptions
import couchbase.options
import dotenv
import os

dotenv.load_dotenv()

# Agent Catalog imports this file once (even if both tools are requested).
# To share (and reuse) Couchbase connections, we can use a top-level variable.
try:
    cluster = couchbase.cluster.Cluster(
        os.getenv("CB_CONN_STRING"),
        couchbase.options.ClusterOptions(
            authenticator=couchbase.auth.PasswordAuthenticator(
                username=os.getenv("CB_USERNAME"),
                password=os.getenv("CB_PASSWORD"),
                certpath=os.getenv("CB_CERTIFICATE"),
            )
        ),
    )
except couchbase.exceptions.CouchbaseException as e:
    print(f"""
        Could not connect to Couchbase cluster!
        This error is going to be swallowed by 'agentc index .', but you will run into issues if you decide to
        run your app!
        Make sure that all Python tools (not just the ones defined in this) are free from unwanted side-effects on
        import.
        {str(e)}
    """)


@agentc.catalog.tool
def find_one_layover_flights(source_airport: str, destination_airport: str) -> list[dict]:
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
    results: list[dict] = list()
    for result in query.rows():
        results.append(result)
    return results


@agentc.catalog.tool
def find_two_layover_flights(source_airport: str, destination_airport: str) -> list[dict]:
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
    results: list[dict] = list()
    for result in query.rows():
        results.append(result)
    return results
