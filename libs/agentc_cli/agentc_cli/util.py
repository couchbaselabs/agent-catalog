import click
import couchbase.cluster

from agentc_core.config import Config


def validate_or_prompt_for_bucket(cfg: Config, bucket: str = None):
    # Buckets specified through the command line will override buckets specified via environment variables.
    if bucket is not None:
        cfg.bucket = bucket

    cluster: couchbase.cluster.Cluster = cfg.Cluster()
    buckets = set([b.name for b in cluster.buckets().get_all_buckets()])
    cluster.close()
    if cfg.bucket is None and cfg.interactive:
        cfg.bucket = click.prompt("Bucket", type=click.Choice(buckets), show_choices=True)

    elif cfg.bucket is not None and cfg.bucket not in buckets:
        raise ValueError(
            "Bucket does not exist!\n"
            f"Available buckets from cluster are: {','.join(buckets)}\n"
            f"Run agentc publish --help for more information."
        )

    elif cfg.bucket is None and not cfg.interactive:
        raise ValueError(
            "Bucket must be specified to publish to the database catalog."
            "Add --bucket BUCKET_NAME to your command or run your command in interactive mode."
        )
