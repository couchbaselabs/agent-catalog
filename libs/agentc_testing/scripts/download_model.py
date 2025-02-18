import pathlib
import sentence_transformers

cache_folder = (pathlib.Path(__file__).parent.parent / "agentc_testing" / "resources" / "models").resolve()
print(f"Cache Folder: {cache_folder}")

sentence_transformers.SentenceTransformer(
    "sentence-transformers/all-MiniLM-L12-v2",
    tokenizer_kwargs={"clean_up_tokenization_spaces": True},
    cache_folder=str(cache_folder.absolute()),
)
