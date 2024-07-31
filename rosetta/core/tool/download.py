import pathlib
import urllib3
import typing
import shutil

open_api_jar_url = (
    'https://repo1.maven.org/maven2/org/openapitools/'
    'openapi-generator-cli/7.7.0/openapi-generator-cli-7.7.0.jar'
)
open_api_jar_filename = 'open-api-generator.jar'


def download_models(embedding_models: typing.List[str]):
    import sentence_transformers

    # Download all embedding models that we need at runtime. Caching is done internally by sentence_transformers.
    # TODO (GLENN): Inform the user if we need to download models somehow.
    for model in embedding_models:
        sentence_transformers.SentenceTransformer(model)


def download_jar_files(libraries_dir: pathlib.Path):
    jar_path = libraries_dir / open_api_jar_url
    if not jar_path.exists():
        with jar_path.open('wb') as fp:
            # Download the OpenAPI client code generator jar.
            r = urllib3.PoolManager().request('GET', open_api_jar_url, preload_content=False)
            shutil.copyfileobj(r, fp)
