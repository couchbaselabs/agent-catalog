import datetime
import os
import pathlib
import pytest
import shutil
import typing

from agentc_core.catalog import CatalogMem
from agentc_core.catalog.index import MetaVersion
from agentc_core.catalog.index import index_catalog
from agentc_core.learned.embedding import EmbeddingModel
from agentc_core.record.descriptor import RecordKind
from agentc_core.version import VersionDescriptor
from agentc_testing.directory import temporary_directory

# This is to keep ruff from falsely flagging this as unused.
_ = temporary_directory


@pytest.mark.smoke
def test_index_tools(temporary_directory: typing.Generator[pathlib.Path, None, None]):
    project_dir = pathlib.Path(temporary_directory)
    project_dir.mkdir(exist_ok=True)

    # Copy files from resources/{tools|prompts} to our temporary directory.
    shutil.copytree(pathlib.Path(__file__).parent / "resources", project_dir, dirs_exist_ok=True)
    libs_dir = pathlib.Path(__file__).parent.parent.parent.parent
    embedding_model = EmbeddingModel(
        sentence_transformers_model_cache=str(
            (libs_dir / "agentc_testing" / "agentc_testing" / "resources" / "models").absolute()
        )
    )

    # Index our catalog.
    os.chdir(temporary_directory)
    catalog_version = VersionDescriptor(
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc), identifier="SOME_CATALOG_VERSION"
    )
    catalog = index_catalog(
        embedding_model=embedding_model,
        meta_version=MetaVersion(schema_version="0.1.0", library_version="0.1.0"),
        catalog_version=catalog_version,
        get_path_version=lambda x: VersionDescriptor(
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc), identifier="SOME_PATH_VERSION"
        ),
        kind="tool",
        catalog_file=pathlib.Path("tools.json"),
        source_dirs=["tools"],
    )
    assert isinstance(catalog, CatalogMem)
    assert catalog_version == catalog.catalog_descriptor.version
    assert not any(x for x in catalog if x.record_kind == RecordKind.Prompt)
    assert len(catalog) == 23


@pytest.mark.smoke
def test_index_prompts(temporary_directory: typing.Generator[pathlib.Path, None, None]):
    project_dir = pathlib.Path(temporary_directory)
    project_dir.mkdir(exist_ok=True)

    # Copy files from resources/{tools|prompts} to our temporary directory.
    shutil.copytree(pathlib.Path(__file__).parent / "resources", project_dir, dirs_exist_ok=True)
    libs_dir = pathlib.Path(__file__).parent.parent.parent.parent
    embedding_model = EmbeddingModel(
        sentence_transformers_model_cache=str(
            (libs_dir / "agentc_testing" / "agentc_testing" / "resources" / "models").absolute()
        )
    )

    # Index our catalog.
    os.chdir(temporary_directory)
    catalog_version = VersionDescriptor(
        timestamp=datetime.datetime.now(tz=datetime.timezone.utc), identifier="SOME_CATALOG_VERSION"
    )
    catalog = index_catalog(
        embedding_model=embedding_model,
        meta_version=MetaVersion(schema_version="0.1.0", library_version="0.1.0"),
        catalog_version=catalog_version,
        get_path_version=lambda x: VersionDescriptor(
            timestamp=datetime.datetime.now(tz=datetime.timezone.utc), identifier="SOME_PATH_VERSION"
        ),
        kind="prompt",
        catalog_file=pathlib.Path("prompts.json"),
        source_dirs=["prompts"],
    )
    assert isinstance(catalog, CatalogMem)
    assert catalog_version == catalog.catalog_descriptor.version
    assert all(x for x in catalog if x.record_kind == RecordKind.Prompt)
    assert len(catalog) == 4
