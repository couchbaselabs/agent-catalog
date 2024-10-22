import abc
import dataclasses
import jinja2
import logging
import os
import typing

from agentc_core.annotation import AnnotationPredicate
from agentc_core.catalog import LATEST_SNAPSHOT_VERSION
from agentc_core.catalog import CatalogBase
from agentc_core.catalog import SearchResult
from agentc_core.prompt.models import JinjaPromptDescriptor
from agentc_core.prompt.models import RawPromptDescriptor
from agentc_core.provider.loader import EntryLoader
from agentc_core.provider.loader import ModelType
from agentc_core.provider.loader import PythonTarget
from agentc_core.record.descriptor import RecordDescriptor
from agentc_core.record.descriptor import RecordKind
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
        func: typing.Any
        meta: RecordDescriptor

    def __init__(
        self,
        catalog: CatalogBase,
        output: os.PathLike = None,
        decorator: typing.Callable[["ToolProvider.ToolResult"], typing.Any] = None,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
        secrets: typing.Optional[dict[str, str]] = None,
        python_version: PythonTarget = PythonTarget.PY_312,
        model_type: ModelType = ModelType.TypingTypedDict,
    ):
        """
        :param catalog: A handle to the catalog. Entries can either be in memory or in Couchbase.
        :param output: Location to place the generated Python stubs (if desired).
        :param decorator: Function to apply to each search result.
        :param refiner: Refiner (reranker / post processor) to use when retrieving tools.
        :param secrets: Map of identifiers to secret values.
        :param python_version: The target Python version for the generated (schema) code.
        :param model_type: The target model type for the generated (schema) code.
        """
        super(ToolProvider, self).__init__(catalog=catalog, refiner=refiner)
        self._tool_cache = dict()
        self._loader = EntryLoader(output=output, python_version=python_version, model_type=model_type)

        # Handle our defaults.
        self.decorator = decorator if decorator is not None else lambda s: s.func
        if secrets is not None:
            # Note: we only register our secrets at instantiation-time.
            for k, v in secrets.items():
                put_secret(k, v)

    def _generate_result(self, tool_descriptor: RecordDescriptor) -> typing.Any:
        return self.decorator(ToolProvider.ToolResult(func=self._tool_cache[tool_descriptor], meta=tool_descriptor))

    def search(
        self,
        query: str,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list[typing.Any]:
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

    def get(self, name: str, snapshot: str = LATEST_SNAPSHOT_VERSION, annotations: str = None) -> typing.Any | None:
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
        prompt: str | jinja2.Template
        tools: typing.Optional[list[typing.Any]]
        meta: RecordDescriptor

    def __init__(
        self,
        tool_provider: ToolProvider,
        catalog: CatalogBase,
        refiner: typing.Callable[[list[SearchResult]], list[SearchResult]] = None,
        jinja2_environment: jinja2.Environment = None,
    ):
        super(PromptProvider, self).__init__(catalog, refiner)
        self.tool_provider = tool_provider
        self.jinja2_environment = (
            jinja2_environment if jinja2_environment is not None else jinja2.Environment(loader=jinja2.BaseLoader)
        )

    def _generate_result(self, prompt_descriptor: RawPromptDescriptor | JinjaPromptDescriptor) -> PromptResult:
        # If our prompt has defined tools, fetch them here.
        tools = None
        if prompt_descriptor.tools is not None:
            tools = list()
            for tool in prompt_descriptor.tools:
                if tool.query is not None:
                    tools += self.tool_provider.search(query=tool.query, annotations=tool.annotations, limit=tool.limit)
                else:  # tool.name is not None
                    tools.append(self.tool_provider.get(name=tool.name, annotations=tool.annotations))

        # If our prompt is a Jinja prompt, return the template.
        if prompt_descriptor.record_kind == RecordKind.JinjaPrompt:
            prompt = self.jinja2_environment.from_string(prompt_descriptor.prompt)
        else:  # prompt_descriptor.record_kind == RecordKind.RawPrompt
            prompt = prompt_descriptor.prompt
        return PromptProvider.PromptResult(prompt=prompt, tools=tools, meta=prompt_descriptor)

    def search(
        self,
        query: str,
        annotations: str = None,
        snapshot: str = LATEST_SNAPSHOT_VERSION,
        limit: typing.Union[int | None] = 1,
    ) -> list["PromptProvider.PromptResult"]:
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.refiner(
            self.catalog.find(query=query, snapshot=snapshot, annotations=annotation_predicate, limit=limit)
        )
        return [self._generate_result(r.entry) for r in results]

    def get(
        self, name: str, snapshot: str = LATEST_SNAPSHOT_VERSION, annotations: str = None
    ) -> typing.Optional["PromptProvider.PromptResult"]:
        annotation_predicate = AnnotationPredicate(query=annotations) if annotations is not None else None
        results = self.catalog.find(name=name, snapshot=snapshot, annotations=annotation_predicate, limit=1)
        return [self._generate_result(r.entry) for r in results][0] if len(results) != 0 else None
