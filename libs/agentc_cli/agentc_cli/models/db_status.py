import pydantic


class DBStatus(pydantic.BaseModel):
    catalog_schema_version: str = "0.0.0"
    embedding_model_used: str = None
    kind: str = None
    project: str = None
    snapshot_annotations: dict = {}
    source_dirs: list = []


"""
[
  {
    "catalog_schema_version": "0.0.0",
    "embedding_model": "sentence-transformers/all-MiniLM-L12-v2",
    "kind": "tool",
    "project": "main",
    "snapshot_annotations": {},
    "source_dirs": [
      "tools"
    ],
    "version": {
      "identifier": "13083dfdfe8be4d178973abd06826c0e53f65f59",
      "is_dirty": false,
      "metadata": null,
      "timestamp": "2024-09-20 09:25:50.569132+00:00",
      "version_system": "git"
    }
  }
]"""
