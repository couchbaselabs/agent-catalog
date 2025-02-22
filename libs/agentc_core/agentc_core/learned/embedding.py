import couchbase.cluster
import couchbase.exceptions
import logging
import pathlib
import pydantic
import typing

from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL
from agentc_core.defaults import DEFAULT_META_COLLECTION_NAME
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_NAME
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_NAME

logger = logging.getLogger(__name__)


class EmbeddingModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    # Embedding models are defined in three distinct ways: explicitly (by name)...
    embedding_model_name: typing.Optional[str] = DEFAULT_EMBEDDING_MODEL

    # ...or implicitly (by path)...
    catalog_path: typing.Optional[pathlib.Path] = None

    # ...or implicitly (by Couchbase).
    cb_bucket: typing.Optional[str] = None
    cb_cluster: typing.Optional[couchbase.cluster.Cluster] = None

    # The actual embedding model object (we won't type this to avoid the sentence transformers import).
    _embedding_model: None

    @pydantic.model_validator(mode="after")
    def validate_bucket_cluster(self) -> "EmbeddingModel":
        if self.cb_bucket is not None and self.cb_cluster is None:
            raise ValueError("cb_cluster must be specified if cb_bucket is specified.")
        if self.cb_bucket is None and self.cb_cluster is not None:
            raise ValueError("cb_bucket must be specified if cb_cluster is specified.")
        return self

    @pydantic.model_validator(mode="after")
    def validate_embedding_model(self) -> "EmbeddingModel":
        # First, we need to grab the name if it does not exist.
        if self.embedding_model_name is None and self.catalog_path is None and self.cb_cluster is None:
            raise ValueError("embedding_model_name, catalog_path, or cb_cluster must be specified.")

        from_catalog_embedding_model_name = None
        if self.catalog_path is not None:
            collected_embedding_model_names = set()

            # Grab our local tool embedding model...
            local_tool_catalog_path = self.catalog_path / DEFAULT_TOOL_CATALOG_NAME
            if local_tool_catalog_path.exists():
                with local_tool_catalog_path.open("r") as fp:
                    local_tool_catalog = CatalogDescriptor.model_validate_json(fp.read())
                collected_embedding_model_names.add(local_tool_catalog.embedding_model)

            # ...and now our local prompt embedding model.
            local_prompt_catalog_path = self.catalog_path / DEFAULT_PROMPT_CATALOG_NAME
            if local_prompt_catalog_path.exists():
                with local_prompt_catalog_path.open("r") as fp:
                    local_prompt_catalog = CatalogDescriptor.model_validate_json(fp.read())
                collected_embedding_model_names.add(local_prompt_catalog.embedding_model)

            if len(collected_embedding_model_names) > 1:
                raise ValueError(
                    f"Multiple embedding models found in local catalogs: " f"{collected_embedding_model_names}"
                )
            elif len(collected_embedding_model_names) == 1:
                from_catalog_embedding_model_name = collected_embedding_model_names.pop()
                logger.debug("Found embedding model %s in local catalogs.", from_catalog_embedding_model_name)

        if self.cb_cluster is not None:
            collected_embedding_model_names = set()

            # TODO (GLENN): There is probably a cleaner way to do this (but this is Pythonic, so...).
            union_subqueries = []
            for kind in ["tool", "prompt"]:
                try:
                    qualified_collection_name = (
                        f"`{self.cb_bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{kind}{DEFAULT_META_COLLECTION_NAME}`"
                    )
                    self.cb_cluster.query(f"""
                        FROM {qualified_collection_name} AS mc
                        SELECT *
                        LIMIT 1
                    """).execute()
                    union_subqueries += [
                        f"""
                            FROM
                                {qualified_collection_name} AS mc
                            SELECT
                                VALUE mc.embedding_model
                            ORDER BY
                                STR_TO_MILLIS(mc.version.timestamp) DESC
                            LIMIT 1
                        """
                    ]
                except (couchbase.exceptions.KeyspaceNotFoundException, couchbase.exceptions.ScopeNotFoundException):
                    continue

            # Gather our embedding models.
            match len(union_subqueries):
                case 1:
                    metadata_query = self.cb_cluster.query(union_subqueries[0])
                case 2:
                    wrapped_queries = [f"({query})" for query in union_subqueries]
                    metadata_query = self.cb_cluster.query(" UNION ALL ".join(wrapped_queries))
                case _:
                    # No metadata collections were found (thus, agentc publish has not been run).
                    logger.debug("No metadata collections found in remote catalogs.")
                    metadata_query = None

            if metadata_query is not None:
                for row in metadata_query:
                    collected_embedding_model_names.add(row)

            if len(collected_embedding_model_names) > 1:
                raise ValueError(
                    f"Multiple embedding models found in remote catalogs: " f"{collected_embedding_model_names}"
                )
            elif len(collected_embedding_model_names) == 1:
                remote_embedding_model_name = collected_embedding_model_names.pop()
                logger.debug("Found embedding model %s in remote catalogs.", remote_embedding_model_name)
                if (
                    from_catalog_embedding_model_name is not None
                    and from_catalog_embedding_model_name != remote_embedding_model_name
                ):
                    raise ValueError(
                        f"Local embedding model {from_catalog_embedding_model_name} does not match "
                        f"remote embedding model {remote_embedding_model_name}!"
                    )
                elif from_catalog_embedding_model_name is None:
                    from_catalog_embedding_model_name = remote_embedding_model_name

        if self.embedding_model_name is None:
            self.embedding_model_name = from_catalog_embedding_model_name
        elif (
            from_catalog_embedding_model_name is not None
            and self.embedding_model_name != from_catalog_embedding_model_name
        ):
            raise ValueError(
                f"Local embedding model {from_catalog_embedding_model_name} does not match "
                f"specified embedding model {self.embedding_model_name}!"
            )
        elif self.embedding_model_name is None and from_catalog_embedding_model_name is None:
            raise ValueError("No embedding model found (run 'agentc index' to download one).")

        # Note: we won't validate the embedding model name because sentence_transformers takes a while to import.
        self._embedding_model = None
        return self

    @property
    def name(self) -> str:
        return self.embedding_model_name

    def encode(self, text: str) -> list[float]:
        if self._embedding_model is None:
            import sentence_transformers

            self._embedding_model = sentence_transformers.SentenceTransformer(
                self.embedding_model_name,
                tokenizer_kwargs={"clean_up_tokenization_spaces": True},
                cache_folder=DEFAULT_MODEL_CACHE_FOLDER,
                local_files_only=False,
            )

        # Normalize embeddings to unit length (only dot-product is computed with Couchbase, so...).
        return self._embedding_model.encode(text, normalize_embeddings=True).tolist()
