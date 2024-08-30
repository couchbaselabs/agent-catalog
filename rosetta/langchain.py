import importlib.util

# We will only expose rosetta_lc if it exists.
if importlib.util.find_spec("rosetta_lc") is not None:
    import langchain_core.language_models.chat_models
    import rosetta.auditor
    import typing

    mod = importlib.import_module("rosetta_lc")

    class AuditType(typing.Protocol):
        def __call__(
            self, chat_model: langchain_core.language_models.chat_models.BaseChatModel, auditor: rosetta.auditor = None
        ) -> langchain_core.language_models.chat_models.BaseChatModel: ...

    # TODO (GLENN): Is there a less messy way to do this that doesn't erase symbols? (to keep IDEs happy)
    audit: AuditType = mod.audit
    IQBackedChatModel: langchain_core.language_models.chat_models.BaseChatModel = mod.IQBackedChatModel
    __all__ = ["audit", "IQBackedChatModel"]

else:
    __all__ = []
