import abc
import logging
import numpy
import pydantic
import scipy.signal
import sklearn.neighbors
import typing

from ..catalog import SearchResult

logger = logging.getLogger(__name__)


class BaseRefiner(abc.ABC):
    @abc.abstractmethod
    def __call__(self, ordered_entries: list[SearchResult]):
        pass


# TODO (GLENN): Fine tune the deepening factor...
class ClosestClusterRefiner(pydantic.BaseModel, BaseRefiner):
    kde_distribution_n: int = pydantic.Field(default=10000, gt=0)
    deepening_factor: float = pydantic.Field(default=0.1, gt=0)
    max_deepen_steps: int = pydantic.Field(default=10, gt=0)
    no_more_than_k: typing.Optional[int] = pydantic.Field(None, gt=0)

    def __call__(self, ordered_entries: list[SearchResult]):
        # We are given tools in the order of most relevant to least relevant -- we need to reverse this list.
        a = numpy.array(sorted([t.delta for t in ordered_entries])).reshape(-1, 1)
        s = numpy.linspace(min(a) - 0.01, max(a) + 0.01, num=self.kde_distribution_n).reshape(-1, 1)

        # Use KDE to estimate our PDF. We are going to iteratively deepen until we get some local extrema.
        for i in range(-1, self.max_deepen_steps):
            working_bandwidth = numpy.float_power(self.deepening_factor, i)
            kde = sklearn.neighbors.KernelDensity(kernel="gaussian", bandwidth=working_bandwidth).fit(X=a)

            # Determine our local minima and maxima in between the cosine similarity range.
            kde_score = kde.score_samples(s)
            first_minimum = scipy.signal.argrelextrema(kde_score, numpy.less)[0]
            first_maximum = scipy.signal.argrelextrema(kde_score, numpy.greater)[0]
            if len(first_minimum) > 0:
                logger.debug(f"Using a bandwidth of {working_bandwidth}.")
                break
            else:
                logger.debug(f"Bandwidth of {working_bandwidth} was not satisfiable. Deepening.")

        if len(first_minimum) < 1:
            logger.debug("Satisfiable bandwidth was not found. Returning original list.")
            return ordered_entries
        else:
            closest_cluster = [t for t in ordered_entries if t.delta > s[first_maximum[-1]]]
            sorted_cluster = sorted(closest_cluster, key=lambda t: t.delta, reverse=True)
            return sorted_cluster[0 : self.no_more_than_k] if self.no_more_than_k is not None else sorted_cluster
