import pytest
import sentence_transformers

from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL
from agentc_core.defaults import DEFAULT_MODEL_CACHE_FOLDER
from agentc_core.learned.embedding import EmbeddingModel


@pytest.mark.smoke
def test_embedding_local_default():
    # download the model
    sentence_transformers.SentenceTransformer(
        DEFAULT_EMBEDDING_MODEL, cache_folder=DEFAULT_MODEL_CACHE_FOLDER, local_files_only=False
    )

    # execute the model
    embedding_model = EmbeddingModel(
        embedding_model_name=DEFAULT_EMBEDDING_MODEL,
    )

    embedding = embedding_model.encode("agentc")
    assert len(embedding) == 384


@pytest.mark.smoke
def test_embedding_local_pretrained():
    # download the model
    sentence_transformers.SentenceTransformer(
        "paraphrase-albert-small-v2", cache_folder=DEFAULT_MODEL_CACHE_FOLDER, local_files_only=False
    )

    # execute the model
    embedding_model = EmbeddingModel(
        embedding_model_name="paraphrase-albert-small-v2",
    )

    embedding = embedding_model.encode("agentc")
    assert len(embedding) == 768
