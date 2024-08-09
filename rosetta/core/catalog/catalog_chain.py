from .catalog_base import CatalogBase, FoundItem


class CatalogChain(CatalogBase):
    """ Represents a chain of catalogs, where all catalogs are searched
        during find(), but results from earlier catalogs take precendence. """

    chain: list[CatalogBase]

    def __init__(self, chain=[]):
        self.chain = chain

    def find(self, query: str, max: int = 1) -> list[FoundItem]:
        results = []

        seen = set() # Keyed by 'source:name'.

        for c in self.chain:
            results_c = c.find(query, max=max)

            for x in results_c:
                source_name = str(x.record_descriptor.source) + ':' + x.record_descriptor.name

                if source_name not in seen:
                    seen.add(source_name)

                    results.append(x)

        if max > 0:
            results = results[:max]

        return results
