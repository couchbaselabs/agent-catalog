import typing

from .catalog_base import CatalogBase, SearchResult


class CatalogChain(CatalogBase):
    """ Represents a chain of catalogs, where all catalogs are searched
        during find(), but results from earlier catalogs take precendence. """

    chain: list[CatalogBase]

    def __init__(self, chain=[]):
        self.chain = chain

    def find(self, query: str, limit: typing.Union[int | None] = 1, tags: list[str] = None) -> list[SearchResult]:
        results = []

        seen = set() # Keyed by 'source:name'.

        for c in self.chain:
            results_c = c.find(query, limit=limit)

            for x in results_c:
                source_name = str(x.entry.source) + ':' + x.entry.name

                if source_name not in seen:
                    seen.add(source_name)

                    results.append(x)

        if limit > 0:
            results = results[:limit]

        return results
