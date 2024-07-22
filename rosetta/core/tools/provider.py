import tempfile
import typing
import pydantic
import pathlib
import importlib
import scipy.signal
import sentence_transformers
import langchain_core.tools
import numpy
import os
import logging
import sklearn
import inspect
import abc
import sys

from .tooling import (
    ToolDescriptor,
    ToolKind
)

from .generator import (
    SQLPPCodeGenerator,
    SemanticSearchCodeGenerator
)

logger = logging.getLogger(__name__)


class _ToolPointer(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    identifier: pydantic.UUID4
    embedding: numpy.ndarray
    tool: ToolDescriptor


class Provider(pydantic.BaseModel, abc.ABC):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    embedding_model: sentence_transformers.SentenceTransformer = pydantic.Field(
        default_factory=lambda: sentence_transformers.SentenceTransformer(os.getenv('DEFAULT_SENTENCE_EMODEL')),
        description="Embedding model used to encode the tool descriptions."
    )

    _tools: typing.List[typing.Type[_ToolPointer]] = list()
    _modules: typing.Dict = dict()

    @abc.abstractmethod
    def semantic(self, objective: str) -> typing.List[langchain_core.tools.StructuredTool]:
        pass

    @abc.abstractmethod
    def get(self, _id: str) -> langchain_core.tools.StructuredTool:
        pass

    def _load_from_source(self, filename: pathlib.Path, entry: ToolDescriptor):
        # TODO (GLENN): We should avoid blindly putting things in our path.
        if not str(filename.parent.absolute()) in sys.path:
            sys.path.append(str(filename.parent.absolute()))

        if filename.stem not in self._modules:
            self._modules[filename.stem] = importlib.import_module(filename.stem)

        # TODO (GLENN): We need a better identifier than just the name and description.
        for name, tool in inspect.getmembers(self._modules[filename.stem]):
            if not isinstance(tool, ToolDescriptor):
                continue
            if name == entry.name and tool.description == entry.description:
                self._tools.append(_ToolPointer(
                    identifier=entry.identifier,
                    embedding=entry.encoding,
                    tool=tool
                ))


class LocalProvider(Provider):
    catalog_location: pathlib.Path

    def __init__(self, /, **data: typing.Any):
        super(LocalProvider, self).__init__(**data)
        with self.catalog_location.open('r') as fp:
            for line in fp:
                entry = ToolDescriptor.model_validate_json(line)
                match entry.kind:
                    case ToolKind.PythonFunction:
                        self._load_from_source(entry.source, entry)

                    case ToolKind.SQLPPQuery:
                        with tempfile.NamedTemporaryFile() as tmp_fp:
                            SQLPPCodeGenerator(
                                tool_descriptor=entry
                            ).write(tmp_fp)

                    case ToolKind.SemanticSearch:
                        with tempfile.NamedTemporaryFile() as tmp_fp:
                            SemanticSearchCodeGenerator(
                                tool_descriptor=entry
                            ).write(tmp_fp)

    def semantic(self, objective: str, k: typing.Union[int | None] = 1) \
            -> typing.List[langchain_core.tools.StructuredTool]:
        # Compute the distance between our tool embeddings and our objective embeddings.
        objective_embedding = self.embedding_model.encode(objective)
        available_tools = [t for t in self._tools]
        tool_deltas = sklearn.metrics.pairwise.cosine_similarity(
            X=[t.embedding for t in available_tools],
            Y=[objective_embedding]
        )

        # Order our tools by their distance to the objective.
        ordered_tools = sorted([
            {'tool': available_tools[i].tool, 'delta': tool_deltas[i]} for i in range(len(tool_deltas))
        ], key=lambda t: t['delta'], reverse=True)
        if k > 0:
            return [t['tool'] for t in ordered_tools][:k]

        else:
            # TODO (GLENN): Get this working!
            a = numpy.array(ordered_tools).reshape(-1, 1)
            s = numpy.linspace(min(a) - 0.01, max(a) + 0.01, num=10000).reshape(-1, 1)

            # Use KDE to estimate our PDF. We are going to iteratively deepen until we get some local extrema.
            deepening_factor = 0.1
            for i in range(-1, 10):
                working_bandwidth = numpy.float_power(deepening_factor, i)
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

    def get(self, _id: str) -> langchain_core.tools.StructuredTool:
        pass


class CapellaProvider(Provider):
    pass
