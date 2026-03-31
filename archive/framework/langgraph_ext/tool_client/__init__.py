"""
tool_client — Transport-agnostic tool contracts (MCP-ready).

Architecture:
    LangGraph Node → ToolClient.call(name, args) → LocalToolClient (dev) / McpToolClient (prod)
                                                     ↓
                                                  ToolRegistry → ToolSpec → handler
"""

from framework.langgraph_ext.tool_client.spec import ToolSpec
from framework.langgraph_ext.tool_client.registry import ToolRegistry
from framework.langgraph_ext.tool_client.envelope import ToolContentBlock, ToolResultEnvelope, ToolResultMeta
from framework.langgraph_ext.tool_client.client import ToolClient, LocalToolClient

__all__ = [
    "ToolSpec",
    "ToolRegistry",
    "ToolContentBlock",
    "ToolResultEnvelope",
    "ToolResultMeta",
    "ToolClient",
    "LocalToolClient",
]
