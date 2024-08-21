import typing

from ..annotation import AnnotationPredicate
from .catalog_base import CatalogBase
from .catalog_base import SearchResult


class CatalogChain(CatalogBase):
    """Represents a chain of catalogs, where all catalogs are searched
    during find(), but results from earlier catalogs take precendence."""

    chain: list[CatalogBase]

    def __init__(self, chain=None):
        self.chain = chain if chain is not None else []

    def find(
        self, query: str, limit: typing.Union[int | None] = 1, annotations: AnnotationPredicate = None
    ) -> list[SearchResult]:
        results = []

        seen = set()  # Keyed by 'source:name'.

        for c in self.chain:
            results_c = c.find(query, limit=limit, annotations=annotations)

            for x in results_c:
                source_name = str(x.entry.source) + ":" + x.entry.name

                if source_name not in seen:
                    seen.add(source_name)

                    results.append(x)

        if limit > 0:
            results = results[:limit]

        return results
