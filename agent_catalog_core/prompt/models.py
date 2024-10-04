import abc
import jinja2
import jinja2.exceptions
import logging
import pathlib
import pydantic
import re
import typing
import yaml

from ..annotation.annotation import AnnotationPredicate
from ..record.descriptor import RecordDescriptor
from ..record.descriptor import RecordKind
from ..version import VersionDescriptor

logger = logging.getLogger(__name__)


class ToolSearchMetadata(pydantic.BaseModel):
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

    # TODO (GLENN): There is similar validation being done in agent_catalog_cmd/find... converge these?
    @pydantic.model_validator(mode="after")
    def name_or_query_must_be_specified(self):
        if self.name is None and self.query is None:
            raise ValueError("Either name or query must be specified!")
        elif self.name is not None and self.query is not None:
            raise ValueError("Both name and query cannot be specified!")
        return self


class _BaseFactory(abc.ABC):
    class PromptMetadata(pydantic.BaseModel):
        name: str
        description: str
        record_kind: typing.Literal[RecordKind.RawPrompt, RecordKind.JinjaPrompt]
        annotations: typing.Optional[dict[str, str] | None] = None
        tools: typing.Optional[list[ToolSearchMetadata] | None] = None

    def __init__(self, filename: pathlib.Path, version: VersionDescriptor):
        """
        :param filename: Name of the file to load the record descriptor from.
        :param version: The version descriptor associated with file describing a set of tools.
        """
        self.filename = filename
        self.version = version

    @abc.abstractmethod
    def __iter__(self):
        pass

    def _get_prompt_metadata(self) -> tuple[dict, str]:
        with self.filename.open("r") as fp:
            matches = re.findall(r"---(.*)---(.*)", fp.read(), re.DOTALL)
            # TODO (GLENN): Make the specification of this front matter optional in the future.
            if len(matches) == 0:
                raise ValueError(f"Malformed input! No front-matter found for {self.filename.name}.")
            front_matter = yaml.safe_load(matches[0][0])
            prompt_text = matches[0][1]
        return front_matter, prompt_text


class RawPromptDescriptor(RecordDescriptor):
    record_kind: typing.Literal[RecordKind.RawPrompt]
    prompt: str
    tools: typing.Optional[list[ToolSearchMetadata] | None] = None

    class Factory(_BaseFactory):
        def __iter__(self) -> typing.Iterable["RawPromptDescriptor"]:
            front_matter, prompt_text = self._get_prompt_metadata()
            metadata = RawPromptDescriptor.Factory.PromptMetadata.model_validate(front_matter)
            descriptor_args = {
                "name": metadata.name,
                "description": metadata.description,
                "record_kind": metadata.record_kind,
                "tools": metadata.tools,
                "prompt": prompt_text,
                "source": self.filename,
                "version": self.version,
            }
            if metadata.annotations is not None:
                descriptor_args["annotations"] = metadata.annotations
            yield RawPromptDescriptor(**descriptor_args)


class JinjaPromptDescriptor(RawPromptDescriptor):
    record_kind: typing.Literal[RecordKind.JinjaPrompt]

    @pydantic.field_validator("prompt")
    @classmethod
    def prompt_must_be_valid_jinja_template(cls, v: str):
        # We'll rely on Jinja to raise an error here.
        try:
            jinja2.Template(source=v)
        except jinja2.exceptions.TemplateError as e:
            raise ValueError("Malformed input! Invalid Jinja template.") from e

    class Factory(_BaseFactory):
        def __iter__(self) -> typing.Iterable["JinjaPromptDescriptor"]:
            front_matter, prompt_text = self._get_prompt_metadata()
            metadata = JinjaPromptDescriptor.Factory.PromptMetadata.model_validate(front_matter)
            descriptor_args = {
                "name": metadata.name,
                "description": metadata.description,
                "record_kind": metadata.record_kind,
                "tools": metadata.tools,
                "prompt": prompt_text,
                "source": self.filename,
                "version": self.version,
            }
            if metadata.annotations is not None:
                descriptor_args["annotations"] = metadata.annotations
            yield JinjaPromptDescriptor(**descriptor_args)
