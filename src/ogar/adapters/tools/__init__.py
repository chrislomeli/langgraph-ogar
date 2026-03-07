"""
tool_client — Transport-agnostic tool contracts (MCP-ready).

Architecture:
    LangGraph Node → ToolClient.call(name, args) → LocalToolClient (dev) / McpToolClient (prod)
                                                     ↓
                                                  ToolRegistry → ToolSpec → handler
"""

from ogar.adapters.tools.spec import ToolSpec
from ogar.adapters.tools.registry import ToolRegistry
from ogar.adapters.tools.envelope import ToolContentBlock, ToolResultEnvelope, ToolResultMeta
from ogar.adapters.tools.client import ToolClient, LocalToolClient

__all__ = [
    "ToolSpec",
    "ToolRegistry",
    "ToolContentBlock",
    "ToolResultEnvelope",
    "ToolResultMeta",
    "ToolClient",
    "LocalToolClient",
]
