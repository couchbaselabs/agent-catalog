import pytest

from agentc_core.defaults import DEFAULT_EMBEDDING_MODEL
from agentc_core.learned.embedding import EmbeddingModel


@pytest.mark.smoke
def test_embedding_local_default():
    embedding_model = EmbeddingModel(
        embedding_model_name=DEFAULT_EMBEDDING_MODEL,
    )

    embedding = embedding_model.encode("agentc")
    assert len(embedding) == 384


@pytest.mark.smoke
def test_embedding_local_pretrained():
    embedding_model = EmbeddingModel(
        embedding_model_name="paraphrase-albert-small-v2",
    )

    embedding = embedding_model.encode("agentc")
    assert len(embedding) == 768
