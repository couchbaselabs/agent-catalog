import importlib.util

# We will only expose rosetta_lc if it exists.
if importlib.util.find_spec("rosetta_lc") is not None:
    mod = importlib.import_module("rosetta_lc")

    # TODO (GLENN): Is there a less messy way to do this that doesn't erase symbols? (to keep IDEs happy)
    audit = mod.audit
    IQBackedChatModel = mod.IQBackedChatModel
    __all__ = ["audit", "IQBackedChatModel"]

else:
    __all__ = []
