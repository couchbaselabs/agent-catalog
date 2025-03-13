import logging
import pathlib
import pydantic
import typing
import yaml

from ..annotation.annotation import AnnotationPredicate
from ..record.descriptor import RecordDescriptor
from ..record.descriptor import RecordKind
from ..version import VersionDescriptor
from agentc_core.record.helper import JSONSchemaValidatingMixin

logger = logging.getLogger(__name__)


class ToolSearchMetadata(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="allow")
    name: typing.Optional[str] = None
    query: typing.Optional[str] = None
    annotations: typing.Optional[str] = None
    limit: typing.Optional[int] = pydantic.Field(default=1, gt=-1)

    @pydantic.field_validator("annotations")
    @classmethod
    def annotations_must_be_valid_string(cls, v: str | None):
        # We raise an error on instantiation here if v is not valid.
        if v is not None:
            AnnotationPredicate(v)
        return v

    # TODO (GLENN): There is similar validation being done in agentc_cli/find... converge these?
    @pydantic.model_validator(mode="after")
    def _name_or_query_must_be_specified(self):
        if self.name is None and self.query is None:
            raise ValueError("Either name or query must be specified!")
        elif self.name is not None and self.query is not None:
            raise ValueError("Both name and query cannot be specified!")
        return self


class PromptDescriptor(RecordDescriptor):
    content: str | dict[str, typing.Any]

    output: typing.Optional[dict] = None
    tools: typing.Optional[list[ToolSearchMetadata]] = pydantic.Field(default_factory=list)
    record_kind: typing.Literal[RecordKind.Prompt]

    class Factory:
        class Metadata(pydantic.BaseModel, JSONSchemaValidatingMixin):
            model_config = pydantic.ConfigDict(frozen=True, use_enum_values=True, extra="allow")

            record_kind: typing.Literal[RecordKind.Prompt]
            name: str
            description: str
            content: str | dict[str, typing.Any]
            output: typing.Optional[str | dict] = None
            tools: typing.Optional[list[ToolSearchMetadata] | None] = None
            annotations: typing.Optional[dict[str, str] | None] = None

            @pydantic.field_validator("output")
            @classmethod
            def value_should_be_valid_json_schema(cls, v: str | dict):
                if v is not None and isinstance(v, str):
                    v = cls.check_if_valid_json_schema_str(v)
                elif v is not None and isinstance(v, dict):
                    v = cls.check_if_valid_json_schema_dict(v)
                else:
                    raise ValueError("Type must be either a string or a YAML dictionary.")
                return v

            @pydantic.field_validator("name")
            @classmethod
            def name_should_be_valid_identifier(cls, v: str):
                if not v.isidentifier():
                    raise ValueError(f"name {v} is not a valid identifier!")
                return v

            @pydantic.field_validator("content")
            @classmethod
            def content_must_only_contain_strings(cls, v: str | dict):
                if isinstance(v, dict):

                    def traverse_dict(working_dict: dict):
                        for _k, _v in working_dict.items():
                            if isinstance(_v, dict):
                                return traverse_dict(_v)
                            elif isinstance(_v, str):
                                return
                            else:
                                raise ValueError("Content must only contain objects and string values.")

                    traverse_dict(v)
                return v

        def __init__(self, filename: pathlib.Path, version: VersionDescriptor):
            """
            :param filename: Name of the file to load the record descriptor from.
            :param version: The version descriptor associated with file describing a set of tools.
            """
            self.filename = filename
            self.version = version

        def __iter__(self) -> typing.Iterable["PromptDescriptor"]:
            with self.filename.open("r") as fp:
                metadata = PromptDescriptor.Factory.Metadata.model_validate(yaml.safe_load(fp))
                if metadata.__pydantic_extra__:
                    logger.warning(
                        f"Extra fields found in {self.filename.name}: {metadata.__pydantic_extra__}. "
                        f"We will ignore these."
                    )
                descriptor_args = {
                    "name": metadata.name,
                    "description": metadata.description,
                    "record_kind": metadata.record_kind,
                    "content": metadata.content,
                    "output": metadata.output,
                    "tools": metadata.tools,
                    "source": self.filename,
                    "version": self.version,
                    "annotations": metadata.annotations,
                }
                yield PromptDescriptor(**descriptor_args)
