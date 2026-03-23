"""
tool_client — Transport-agnostic tool contracts (MCP-ready).

Architecture:
    LangGraph Node → ToolClient.call(name, args) → LocalToolClient (dev) / McpToolClient (prod)
                                                     ↓
                                                  ToolRegistry → ToolSpec → handler
"""

from conversation_engine.infrastructure.tool_client.spec import ToolSpec
from conversation_engine.infrastructure.tool_client.registry import ToolRegistry
from conversation_engine.infrastructure.tool_client.envelope import (
    ToolContentBlock,
    ToolResultEnvelope,
    ToolResultMeta,
)
from conversation_engine.infrastructure.tool_client.client import (
    ToolClient,
    ToolCallError,
    LocalToolClient,
)

__all__ = [
    "ToolSpec",
    "ToolRegistry",
    "ToolContentBlock",
    "ToolResultEnvelope",
    "ToolResultMeta",
    "ToolClient",
    "ToolCallError",
    "LocalToolClient",
]
