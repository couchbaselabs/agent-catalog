import abc
import logging
import pathlib
import pydantic
import typing
import yaml

from ..embedding.embedding import EmbeddingModel
from ..prompt.models import JinjaPromptDescriptor
from ..prompt.models import RawPromptDescriptor
from ..record.descriptor import RecordDescriptor
from ..record.descriptor import RecordKind
from ..tool.descriptor import HTTPRequestToolDescriptor
from ..tool.descriptor import PythonToolDescriptor
from ..tool.descriptor import SemanticSearchToolDescriptor
from ..tool.descriptor import SQLPPQueryToolDescriptor

logger = logging.getLogger(__name__)


# TODO: We should use something other than ValueError,
# such as by capturing line numbers, etc?
class BaseFileIndexer(pydantic.BaseModel):
    @abc.abstractmethod
    def start_descriptors(
        self, filename: pathlib.Path, get_path_version
    ) -> typing.Tuple[list[ValueError], list[RecordDescriptor]]:
        """Returns zero or more 'bare' catalog item descriptors for a filename,
        and/or return non-fatal or 'keep-on-going' errors if any encountered.

        The returned descriptors are 'bare' in that they only capture
        immediately available information and properties. Any slow
        operators such as LLM augmentation, vector embeddings, etc. are
        handled by other methods & processing phases that are called later.

        A 'keep-on-going' error means the top level command should
        ultimately error, but more processing on other files might
        still be attempted to increase the user's productivity --
        e.g., show the user multiple error messages instead of
        giving up on the very first encountered error.
        """
        pass


class DotPyFileIndexer(BaseFileIndexer):
    def start_descriptors(
        self, filename: pathlib.Path, get_path_version
    ) -> typing.Tuple[list[ValueError], list[RecordDescriptor]]:
        """Returns zero or more 'bare' catalog item descriptors
        for a *.py, and/or returns 'keep-on-going' errors
        if any encountered.
        """
        factory = PythonToolDescriptor.Factory(filename=filename, version=get_path_version(filename))
        return None, list(factory)


class DotSqlppFileIndexer(BaseFileIndexer):
    def start_descriptors(
        self, filename: pathlib.Path, get_path_version
    ) -> typing.Tuple[list[ValueError], list[RecordDescriptor]]:
        """Returns zero or 1 'bare' catalog item descriptors
        for a *.sqlpp, and/or return 'keep-on-going' errors
        if any encountered.
        """
        factory = SQLPPQueryToolDescriptor.Factory(filename=filename, version=get_path_version(filename))
        return None, list(factory)


class DotYamlFileIndexer(BaseFileIndexer):
    def start_descriptors(
        self, filename: pathlib.Path, get_version
    ) -> typing.Tuple[list[ValueError], list[RecordDescriptor]]:
        """Returns zero or more 'bare' catalog item descriptors
        for a *.yaml, and/or return 'keep-on-going' errors
        if any encountered.
        """
        # All we need here is the record_kind.
        with filename.open("r") as fp:
            parsed_desc = yaml.safe_load(fp)
            if "record_kind" not in parsed_desc:
                logger.warning(
                    f"Encountered .yaml file with unknown record_kind field. "
                    f"Not indexing {str(filename.absolute())}."
                )
                return None, []
            record_kind = parsed_desc["record_kind"]

        factory_args = {"filename": filename, "version": get_version(filename)}
        match record_kind:
            case RecordKind.SemanticSearch:
                return None, list(SemanticSearchToolDescriptor.Factory(**factory_args))

            case RecordKind.HTTPRequest:
                return None, list(HTTPRequestToolDescriptor.Factory(**factory_args))

            case _:
                logger.warning(
                    f"Encountered .yaml file with unknown record_kind field. "
                    f"Not indexing {str(filename.absolute())}."
                )
                return None, list()


class DotPromptFileIndexer(BaseFileIndexer):
    def start_descriptors(
        self, filename: pathlib.Path, get_version
    ) -> typing.Tuple[list[ValueError], list[RecordDescriptor]]:
        return None, list(RawPromptDescriptor.Factory(filename=filename, version=get_version(filename)))


class DotJinjaFileIndexer(BaseFileIndexer):
    def start_descriptors(
        self, filename: pathlib.Path, get_path_version
    ) -> typing.Tuple[list[ValueError], list[RecordDescriptor]]:
        return None, list(JinjaPromptDescriptor.Factory(filename=filename, version=get_path_version(filename)))


source_indexers = {
    "*.py": DotPyFileIndexer(),
    "*.sqlpp": DotSqlppFileIndexer(),
    "*.yaml": DotYamlFileIndexer(),
    "*.prompt": DotPromptFileIndexer(),
    "*.jinja": DotJinjaFileIndexer(),
}


def augment_descriptor(descriptor: RecordDescriptor) -> list[ValueError]:
    """Augments a single catalog item descriptor (in-place, destructive),
    with additional information, such as generated by an LLM,
    and/or return 'keep-on-going' errors if any encountered.
    """

    # TODO: Different source file descriptor might have
    # different ways of augmenting a descriptor?

    return None


def vectorize_descriptor(descriptor: RecordDescriptor, embedding_model: EmbeddingModel) -> list[ValueError]:
    """Adds vector embeddings to a single catalog item descriptor (in-place,
    destructive), and/or return 'keep-on-going' errors if any encountered.
    """

    # TODO: Different source file models might have different ways
    # to compute & add vector embedding(s), perhaps by using additional
    # fields besides description?

    descriptor.embedding = embedding_model.encode(descriptor.description)

    return None
