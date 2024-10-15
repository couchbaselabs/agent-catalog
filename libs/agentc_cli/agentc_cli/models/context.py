import dataclasses

from agentc_core.defaults import DEFAULT_ACTIVITY_FOLDER
from agentc_core.defaults import DEFAULT_CATALOG_FOLDER
from agentc_core.defaults import DEFAULT_VERBOSITY_LEVEL


@dataclasses.dataclass
class Context:
    catalog: str = DEFAULT_CATALOG_FOLDER
    activity: str = DEFAULT_ACTIVITY_FOLDER
    verbose: int = DEFAULT_VERBOSITY_LEVEL
