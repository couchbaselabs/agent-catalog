import agentc_core.activity.auditor as auditor
import agentc_core.catalog as catalog
import agentc_core.provider as provider
import agentc_core.tool as tool

__all__ = ["tool", "provider", "catalog", "auditor"]

# This is the version of the SDK tool / library. For the version of the catalog data format, see
# agentc_core.catalog.VERSION_CATALOG.
#
# NOTE: This should be replaced during build/packaging by the output of `git describe --long --always`.
# For example: "v0.1.0-0-g6f9305e".
__version__ = "vMajor.Minor.Micro-N-GITSHA"
