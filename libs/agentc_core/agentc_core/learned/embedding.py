import agentc_core.learned.model
import couchbase.cluster
import couchbase.exceptions
import logging
import pathlib
import pydantic
import typing

from agentc_core.catalog.descriptor import CatalogDescriptor
from agentc_core.defaults import DEFAULT_CATALOG_METADATA_COLLECTION
from agentc_core.defaults import DEFAULT_CATALOG_SCOPE
from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL_NAME
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.defaults import DEFAULT_PROMPT_CATALOG_FILE
from agentc_core.defaults import DEFAULT_TOOL_CATALOG_FILE

logger = logging.getLogger(__name__)


class EmbeddingModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    # Embedding models are defined in three distinct ways: explicitly (by name)...
    embedding_model_name: typing.Optional[str] = DEFAULT_EMBEDDING_MODEL_NAME
    embedding_model_url: typing.Optional[str] = None
    embedding_model_auth: typing.Optional[str] = None

    # ...or implicitly (by path)...
    catalog_path: typing.Optional[pathlib.Path] = None

    # ...or implicitly (by Couchbase).
    cb_bucket: typing.Optional[str] = None
    cb_cluster: typing.Optional[couchbase.cluster.Cluster] = None

    # Sentence-transformers-specific parameters.
    sentence_transformers_model_cache: typing.Optional[str] = DEFAULT_MODEL_CACHE_FOLDER
    sentence_transformers_retry_attempts: typing.Optional[int] = 3

    # The actual embedding model object (we won't type this to avoid the sentence transformers import).
    _embedding_model: None = None

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

        from_catalog_embedding_model = None
        if self.catalog_path is not None:
            collected_embedding_models = set()

            # Grab our local tool embedding model...
            local_tool_catalog_path = self.catalog_path / DEFAULT_TOOL_CATALOG_FILE
            if local_tool_catalog_path.exists():
                with local_tool_catalog_path.open("r") as fp:
                    local_tool_catalog = CatalogDescriptor.model_validate_json(fp.read())
                collected_embedding_models.add(local_tool_catalog.embedding_model)

            # ...and now our local prompt embedding model.
            local_prompt_catalog_path = self.catalog_path / DEFAULT_PROMPT_CATALOG_FILE
            if local_prompt_catalog_path.exists():
                with local_prompt_catalog_path.open("r") as fp:
                    local_prompt_catalog = CatalogDescriptor.model_validate_json(fp.read())
                collected_embedding_models.add(local_prompt_catalog.embedding_model)

            if len(collected_embedding_models) > 1:
                raise ValueError(f"Multiple embedding models found in local catalogs: " f"{collected_embedding_models}")
            elif len(collected_embedding_models) == 1:
                from_catalog_embedding_model = collected_embedding_models.pop()
                logger.debug("Found embedding model %s in local catalogs.", from_catalog_embedding_model)

        if self.cb_cluster is not None:
            collected_embedding_models = set()

            # Gather our embedding models.
            try:
                qualified_collection_name = (
                    f"`{self.cb_bucket}`.`{DEFAULT_CATALOG_SCOPE}`.`{DEFAULT_CATALOG_METADATA_COLLECTION}`"
                )
                metadata_query = self.cb_cluster.query(f"""
                    FROM
                        {qualified_collection_name} AS mc
                    SELECT
                        VALUE mc.embedding_model
                    ORDER BY
                        mc.version.timestamp DESC
                    LIMIT 1
                """).execute()
                for row in metadata_query:
                    collected_embedding_models.add(agentc_core.learned.model.EmbeddingModel.model_validate(row))

            except (couchbase.exceptions.KeyspaceNotFoundException, couchbase.exceptions.ScopeNotFoundException) as e:
                # No metadata collections were found (thus, agentc publish has not been run).
                logger.debug(f"Metadata collection not found in remote catalog. Swallowing exception {str(e)}.")

            if len(collected_embedding_models) == 1:
                remote_embedding_model = collected_embedding_models.pop()
                logger.debug("Found embedding model %s in remote catalog.", remote_embedding_model)
                if from_catalog_embedding_model is not None and from_catalog_embedding_model != remote_embedding_model:
                    raise ValueError(
                        f"Local embedding model {from_catalog_embedding_model} does not match "
                        f"remote embedding model {remote_embedding_model}!"
                    )
                elif from_catalog_embedding_model is None:
                    from_catalog_embedding_model = remote_embedding_model

        if self.embedding_model_name is None:
            self.embedding_model_name = from_catalog_embedding_model.name
            self.embedding_model_url = from_catalog_embedding_model.base_url
        elif (
            from_catalog_embedding_model is not None and self.embedding_model_name != from_catalog_embedding_model.name
        ):
            raise ValueError(
                f"Local embedding model {from_catalog_embedding_model.name} does not match "
                f"specified embedding model {self.embedding_model_name}!"
            )
        elif self.embedding_model_name is None and from_catalog_embedding_model is None:
            raise ValueError("No embedding model found (run 'agentc init' to download one).")

        # Note: we won't validate the embedding model name because sentence_transformers takes a while to import.
        self._embedding_model = None
        return self

    @property
    def name(self) -> str:
        return self.embedding_model_name

    def load(self) -> None:
        if self.embedding_model_url is not None:
            import openai

            open_ai_client = openai.OpenAI(base_url=self.embedding_model_url, api_key=self.embedding_model_auth)

            def _encode(_text: str) -> list[float]:
                return (
                    open_ai_client.embeddings.create(
                        model=self.embedding_model_name, input=_text, encoding_format="float"
                    )
                    .data[0]
                    .embedding
                )

            self._embedding_model = _encode

        else:
            import sentence_transformers

            embedding_model = None
            last_error: Exception = None
            for i in range(self.sentence_transformers_retry_attempts):
                try:
                    embedding_model = sentence_transformers.SentenceTransformer(
                        self.embedding_model_name,
                        tokenizer_kwargs={"clean_up_tokenization_spaces": True},
                        cache_folder=self.sentence_transformers_model_cache,
                        local_files_only=i == 0,
                    )
                    break

                except OSError as e:
                    logger.warning(f"Failed to load embedding model {self.embedding_model_name} (attempt {i}): {e}")
                    last_error = e

            # If we still don't have an embedding model, raise an exception.
            if embedding_model is None:
                raise last_error

            else:

                def _encode(_text: str) -> list[float]:
                    return embedding_model.encode(_text, normalize_embeddings=True).tolist()

                self._embedding_model = _encode

    def encode(self, text: str) -> list[float]:
        if self._embedding_model is None:
            self.load()

        # Normalize embeddings to unit length (only dot-product is computed with Couchbase, so...).
        return self._embedding_model(text)
