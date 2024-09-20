import importlib.util
import langchain_core.language_models.chat_models
import logging
import rosetta.auditor
import typing

logger = logging.getLogger(__name__)

# We will only expose rosetta_lc if it exists.
if importlib.util.find_spec("rosetta_lc") is not None:
    mod = importlib.import_module("rosetta_lc")

    # TODO (GLENN): Is there a less messy way to do this that doesn't erase symbols? (to keep IDEs happy)
    class AuditType(typing.Protocol):
        def __call__(
            self,
            chat_model: langchain_core.language_models.chat_models.BaseChatModel,
            session: typing.AnyStr,
            auditor: rosetta.auditor,
        ) -> langchain_core.language_models.chat_models.BaseChatModel: ...

    audit: AuditType = mod.audit

else:

    def audit(
        chat_model: langchain_core.language_models.chat_models.BaseChatModel,
        session: typing.AnyStr,
        auditor: rosetta.auditor,
    ) -> langchain_core.language_models.chat_models.BaseChatModel:
        logger.warning("rosetta_lc not found! Returning chat_model without modification.")
        return chat_model


__all__ = ["audit"]
