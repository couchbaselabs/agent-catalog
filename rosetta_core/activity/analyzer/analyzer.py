import couchbase.cluster
import enum


class Metric(enum.StrEnum):
    FAITHFULNESS = "faithfulness"
    ANSWER_RELEVANCY = "answer-relevancy"
    CONTEXT_UTILIZATION = "context-utilization"


class Analyzer:
    def __init__(
        self,
        metrics: list[Metric],
        cluster: couchbase.cluster.Cluster,
        bucket: str,
        scope: str,
        log_collection: str,
        out_collection: str,
    ):
        self.metrics = metrics
        self.cluster = cluster
        self.bucket = bucket
        self.scope = scope
        self.log_collection = log_collection
        self.out_collection = out_collection

    # TODO (GLENN): Finish this...
    def _setup(self):
        # Define the output collection if it doesn't exist...
        create_dataset = f"""
            CREATE COLLECTION `{self.bucket}`.`{self.scope}`.`{self.out_collection}` IF NOT EXISTS;
        """
        self.cluster.query(create_dataset).execute()

    def _accept_session(
        self,
    ):
        pass

    def run(self):
        # For each grouping (i.e., generation) in the log collection...

        # ...run the desired metrics.
        pass
