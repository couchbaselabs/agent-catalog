from ..record.descriptor import RecordDescriptor
from .catalog_base import CatalogBase


class CatalogChain(CatalogBase):
    """ Represents a chain of catalogs, where all catalogs are searched
        during find(), but results from earlier catalogs take precendence. """

    chain: list[CatalogBase]

    def __init__(self, chain=[]):
        self.chain = chain

    def find(self, query: str, max: int = 1) -> list[RecordDescriptor]:
        results = []

        for c in self.chain:
            results_c = c.find(query, max=max)

            # TODO: Filter out entries from results_c which
            # are shadowed by the entries in the existing results.

            results += results_c

        if max > 0:
            results = results[:max]

        return results
