from ..record.descriptor import RecordDescriptor
from .catalog_base import CatalogBase


class CatalogChain(CatalogBase):
    """ Represents a chain of catalogs, where all catalogs are searched
        during find(), but results from earlier catalogs take precendence. """

    chain: list[CatalogBase]

    def __init__(self, chain):
        self.chain = chain

    def find(self, query) -> list[RecordDescriptor]:
        # TODO: This might roughly look something like...

        results = []

        for c in self.chain:
            results_c = c.find(query)

            # TODO: Filter out entries from results_c which
            # are shadowed by the entries in the existing results.

            results += results_c

        return results
