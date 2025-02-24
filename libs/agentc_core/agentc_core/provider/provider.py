import abc
import dataclasses
import logging
import os
import typing

from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog.implementations.base import CatalogBase
from agentc_core.catalog.implementations.base import SearchResult
from agentc_core.config import LATEST_SNAPSHOT_VERSION
from agentc_core.prompt.models import PromptDescriptor
from agentc_core.provider.loader import EntryLoader
from agentc_core.provider.loader import ModelType
from agentc_core.provider.loader import PythonTarget
from agentc_core.record.descriptor import RecordDescriptor
from agentc_core.secrets import put_secret

logger = logging.getLogger(__name__)


class BaseProvider(abc.ABC):
    def __init__(
        self,
        catalog: CatalogBase,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
    ):
        self.catalog = catalog
        self.refiner = refiner if refiner is not None else lambda s: s

    @abc.abstractmethod
    def search(self, query: str, annotations: str = None, limit: typing.Union[int | None] = 1):
        pass

    @abc.abstractmethod
    def get(self, name: str, annotations: str = None):
        pass


class ToolProvider(BaseProvider):
    @dataclasses.dataclass
    class ToolResult:
        func: typing.Callable
        meta: RecordDescriptor

    def __init__(
        self,
        catalog: CatalogBase,
        output: os.PathLike = None,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
        secrets: typing.Optional[dict[str, str]] = None,
        python_version: PythonTarget = PythonTarget.PY_312,
        model_type: ModelType = ModelType.TypingTypedDict,
    ):
        """
        :param catalog: A handle to the catalog. Entries can either be in memory or in Couchbase.
        :param output: Location to place the generated Python stubs (if desired).
        :param refiner: Refiner (reranker / post processor) to use when retrieving tools.
        :param secrets: Map of identifiers to secret values.
        :param python_version: The target Python version for the generated (schema) code.
        :param model_type: The target model type for the generated (schema) code.
        """
        super(ToolProvider, self).__init__(catalog=catalog, refiner=refiner)
        self._tool_cache = dict()
        self._loader = EntryLoader(output=output, python_version=python_version, model_type=model_type)

        # Handle our defaults.
        if secrets is not None:
            # Note: we only register our secrets at instantiation-time.
            for k, v in secrets.items():
                put_secret(k, v)

    def _generate_result(self, tool_descriptor: RecordDescriptor) -> typing.Any:
        return ToolProvider.ToolResult(func=self._tool_cache[tool_descriptor], meta=tool_descriptor)

    def search(
        self,
        query: str,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[ToolResult]:
        """
        :param query: A string to search the catalog with.
        :param annotations: An annotation query string in the form of KEY=VALUE (AND|OR KEY=VALUE)*.
        :param snapshot: The snapshot version to search.
        :param limit: The maximum number of results to return.
        :return: A list of tools (Python functions).
        """
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.refiner(
            self.catalog.find(query=query, snapshot=snapshot, annotations=annotation_predicate, limit=limit)
        )

        # Load all tools that we have not already cached.
        non_cached_results = [f.entry for f in results if f.entry not in self._tool_cache]
        for record_descriptor, tool in self._loader.load(non_cached_results):
            self._tool_cache[record_descriptor] = tool

        # Return the tools from the cache.
        return [self._generate_result(x.entry) for x in results]

    def get(self, name: str, snapshot: str = LATEST_SNAPSHOT_VERSION, annotations: str = None) -> ToolResult | None:
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.catalog.find(name=name, snapshot=snapshot, annotations=annotation_predicate, limit=1)

        # Load all tools that we have not already cached.
        non_cached_results = [f.entry for f in results if f.entry not in self._tool_cache]
        for record_descriptor, tool in self._loader.load(non_cached_results):
            self._tool_cache[record_descriptor] = tool

        # Return the tools from the cache.
        return [self._generate_result(x.entry) for x in results][0] if len(results) != 0 else None


class PromptProvider(BaseProvider):
    @dataclasses.dataclass
    class PromptResult:
        content: str | dict
        tools: typing.Optional[list[ToolProvider.ToolResult]]
        output: typing.Optional[dict]
        meta: RecordDescriptor

    def __init__(
        self,
        catalog: CatalogBase,
        tool_provider: ToolProvider = None,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
    ):
        super(PromptProvider, self).__init__(catalog, refiner)
        self.tool_provider = tool_provider
        if self.tool_provider is None:
            logger.warning("PromptProvider has been instantiated without a ToolProvider.")

    def _generate_result(self, prompt_descriptor: PromptDescriptor) -> PromptResult:
        # If our prompt has defined tools, fetch them here.
        tools = None
        if prompt_descriptor.tools is not None:
            if self.tool_provider is None:
                raise ValueError(
                    "Tool(s) have been defined in the prompt, but no ToolProvider has been provided. "
                    "If this is a new repo, please run `agentc index tool` to first index your tools."
                )
            tools = list()
            for tool in prompt_descriptor.tools:
                if tool.query is not None:
                    tools += self.tool_provider.search(query=tool.query, annotations=tool.annotations, limit=tool.limit)
                else:  # tool.name is not None
                    tools.append(self.tool_provider.get(name=tool.name, annotations=tool.annotations))

        return PromptProvider.PromptResult(
            content=prompt_descriptor.content,
            output=prompt_descriptor.output,
            tools=tools,
            meta=prompt_descriptor,
        )

    def search(
        self,
        query: str,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[PromptResult]:
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.refiner(
            self.catalog.find(query=query, snapshot=snapshot, annotations=annotation_predicate, limit=limit)
        )
        return [self._generate_result(r.entry) for r in results]

    def get(
        self, name: str, snapshot: str = LATEST_SNAPSHOT_VERSION, annotations: str = None
    ) -> typing.Optional[PromptResult]:
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.catalog.find(name=name, snapshot=snapshot, annotations=annotation_predicate, limit=1)
        return [self._generate_result(r.entry) for r in results][0] if len(results) != 0 else None
