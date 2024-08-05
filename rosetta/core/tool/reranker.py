import typing
import pydantic
import scipy.signal
import sklearn.neighbors
import numpy
import dataclasses
import logging
import langchain_core.tools

logger = logging.getLogger(__name__)


# Note: Numpy and Pydantic don't really play well together...
@dataclasses.dataclass
class ToolWithEmbedding:
    identifier: str
    embedding: numpy.ndarray
    tool: langchain_core.tools.StructuredTool


@dataclasses.dataclass
class ToolWithDelta:
    tool: langchain_core.tools.StructuredTool
    delta: float


# TODO (GLENN): Fine tune the deepening factor...
class ClosestClusterReranker(pydantic.BaseModel):
    kde_distribution_n: int = pydantic.Field(default=10000, gt=0)
    deepening_factor: float = pydantic.Field(default=0.1, gt=0)
    max_deepen_steps: int = pydantic.Field(default=10, gt=0)
    no_more_than_k: typing.Optional[int] = pydantic.Field(None, gt=0)

    def __call__(self, ordered_tools: list[ToolWithDelta]):
        # We are given tools in the order of most relevant to least relevant -- we need to reverse this list.
        a = numpy.array(sorted([t.delta for t in ordered_tools])).reshape(-1, 1)
        s = numpy.linspace(min(a) - 0.01, max(a) + 0.01, num=self.kde_distribution_n).reshape(-1, 1)

        # Use KDE to estimate our PDF. We are going to iteratively deepen until we get some local extrema.
        for i in range(-1, self.max_deepen_steps):
            working_bandwidth = numpy.float_power(self.deepening_factor, i)
            kde = sklearn.neighbors.KernelDensity(
                kernel='gaussian',
                bandwidth=working_bandwidth
            ).fit(X=a)

            # Determine our local minima and maxima in between the cosine similarity range.
            kde_score = kde.score_samples(s)
            first_minimum = scipy.signal.argrelextrema(kde_score, numpy.less)[0]
            first_maximum = scipy.signal.argrelextrema(kde_score, numpy.greater)[0]
            if len(first_minimum) > 0:
                logger.debug(f'Using a bandwidth of {working_bandwidth}.')
                break
            else:
                logger.debug(f'Bandwidth of {working_bandwidth} was not satisfiable. Deepening.')

        if len(first_minimum) < 1:
            logger.warning('Satisfiable bandwidth was not found. Returning original list.')
            return ordered_tools
        else:
            closest_cluster = [t for t in ordered_tools if t.delta > s[first_maximum[-1]]]
            sorted_cluster = sorted(closest_cluster, key=lambda t: t.delta, reverse=True)
            return sorted_cluster[0:self.no_more_than_k] if self.no_more_than_k is not None else sorted_cluster
