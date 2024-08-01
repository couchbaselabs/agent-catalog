import pydantic
import scipy.signal
import sklearn
import numpy
import dataclasses
import logging
import langchain_core.tools
import typing

logger = logging.getLogger(__name__)


# Note: Numpy and Pydantic don't really play well together...
@dataclasses.dataclass
class ToolWithEmbedding:
    identifier: pydantic.UUID4
    embedding: numpy.ndarray
    tool: langchain_core.tools.StructuredTool


@dataclasses.dataclass
class ToolWithDelta:
    tool: langchain_core.tools.StructuredTool
    delta: float


# TODO (GLENN): Get this working!
class ClosestClusterReranker(pydantic.BaseModel):
    kde_distribution_n: int = pydantic.Field(default=10000, gt=0)
    deepening_factor: float = pydantic.Field(default=0.1, gt=0)
    max_deepen_steps: int = pydantic.Field(default=10, gt=0)

    def __call__(self, ordered_tools: typing.List[ToolWithDelta]):
        a = numpy.array(ordered_tools).reshape(-1, 1)
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
            raise RuntimeError('Could not find satisfiable bandwidth!!')
        return []
