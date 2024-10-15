import agent_catalog.auditor
import importlib.util
import langchain_core.language_models.chat_models
import logging
import typing

logger = logging.getLogger(__name__)

# We will only expose agentc_langchain if it exists.
if importlib.util.find_spec("agentc_langchain") is not None:
    mod = importlib.import_module("agentc_langchain")

    # TODO (GLENN): Is there a less messy way to do this that doesn't erase symbols? (to keep IDEs happy)
    class AuditType(typing.Protocol):
        def __call__(
            self,
            chat_model: langchain_core.language_models.chat_models.BaseChatModel,
            session: typing.AnyStr,
            auditor: agent_catalog.auditor,
        ) -> langchain_core.language_models.chat_models.BaseChatModel: ...

    audit: AuditType = mod.audit

else:

    def audit(
        chat_model: langchain_core.language_models.chat_models.BaseChatModel,
        session: typing.AnyStr,
        auditor: agent_catalog.auditor,
    ) -> langchain_core.language_models.chat_models.BaseChatModel:
        logger.warning("agentc_langchain not found! Returning chat_model without modification.")
        return chat_model


__all__ = ["audit"]
