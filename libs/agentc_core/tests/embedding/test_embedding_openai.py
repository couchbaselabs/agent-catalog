import os
import pytest

from agentc_core.learned.embedding import EmbeddingModel


@pytest.mark.smoke
def test_embedding_openai():
    embedding_model = EmbeddingModel(
        embedding_model_name="text-embedding-3-small",
        embedding_model_url="https://api.openai.com/v1",
        embedding_model_auth=os.getenv("OPENAI_API_KEY"),
    )

    embedding = embedding_model.encode("agentc")
    assert len(embedding) == 1536
