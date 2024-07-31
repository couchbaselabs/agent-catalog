import abc
import io
import json
import sentence_transformers
import os
import uuid
import pathlib
import pydantic

from .prompt import Prompt


class Tracer(pydantic.BaseModel, abc.ABC):
    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    version: str = pydantic.Field(
        default_factory=lambda: uuid.uuid4().hex,
        description="(Agent) version to associate with each accepted prompt."
    )
    embedding_model: sentence_transformers.SentenceTransformer = pydantic.Field(
        description="Embedding model used to encode the prompts themselves."
    )

    @abc.abstractmethod
    def __call__(self, prompt: str) -> str:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class LocalTracer(Tracer):
    catalog_file: pathlib.Path
    _catalog_fp: io.StringIO = None

    def __enter__(self):
        self._catalog_fp = self.catalog_file.open('a')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._catalog_fp.close()

    def __call__(self, prompt: str) -> str:
        # TODO (GLENN): Handle large prompts.
        embedding = self.embedding_model.encode(prompt).tolist()
        json.dump(Prompt(
            version=self.version,
            embedding=embedding,
            prompt=prompt,
        ).dict(), self._catalog_fp)
        self._catalog_fp.write('\n')
        return prompt


class CouchbaseTracer(Tracer):
    pass
