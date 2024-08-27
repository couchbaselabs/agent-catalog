import click
import logging
import typing

from ..descriptor import CatalogDescriptor
from .base import CatalogBase
from .base import SearchResult
from rosetta_cmd.models import Keyspace
from rosetta_core.annotation import AnnotationPredicate
from rosetta_util.query import execute_query

logger = logging.getLogger(__name__)


# noinspection SqlNoDataSourceInspection
class CatalogDB(CatalogBase):
    """Represents a catalog stored in a database."""

    # TODO: This probably has fields of conn info, etc.

    def find(
        self,
        query: str,
        limit: typing.Union[int | None] = 1,
        annotations: AnnotationPredicate = None,
        bucket: str = "",
        kind: str = "tool",
        snapshot_id: typing.Union[str | None] = "all",
        cluster: any = "",
        keyspace: Keyspace = None,
    ) -> list[SearchResult]:
        """Returns the catalog items that best match a query."""

        # Get all items from catalog
        if snapshot_id != "all":
            filter_records_query = (
                f"SELECT * FROM `{bucket}`.`rosetta-catalog`.`{kind}_catalog`",
                f'WHERE catalog_identifier="{snapshot_id}";',
            )
        else:
            filter_records_query = f"SELECT * FROM `{bucket}`.`rosetta-catalog`.`{kind}_catalog`;"

        res, err = execute_query(cluster, keyspace, filter_records_query)
        if err is not None:
            click.secho(f"ERROR: {err}", fg="red")
            return []

        catalog = CatalogDescriptor()
        for row in res.rows():
            catalog.model_validate_json(row)

        print(catalog[0])

        # TODO: If annotations have been specified, prune all tools that do not possess these annotations.

        # TODO: Perform semantic search

        # TODO: Order results

        # TODO: Apply our limit clause.
        # if limit > 0:
        #     results = results[:limit]
        # return results

        return []
