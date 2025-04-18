import pathlib
import sentence_transformers
import time

cache_folder = (pathlib.Path(__file__).parent.parent / "agentc_testing" / "resources" / "models").resolve()
print(f"Cache Folder: {cache_folder}")

for i in range(3):
    try:
        print(f"Downloading the sentence-transformers/all-MiniLM-L12-v2 model. Attempt #{i + 1}")
        sentence_transformers.SentenceTransformer(
            "sentence-transformers/all-MiniLM-L12-v2",
            tokenizer_kwargs={"clean_up_tokenization_spaces": True},
            cache_folder=str(cache_folder.absolute()),
        )
        break

    except OSError as e:
        print(f"Download failed: {e}. Retrying in 10 seconds...")
        time.sleep(10)
