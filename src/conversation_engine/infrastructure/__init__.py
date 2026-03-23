"""
infrastructure — Reusable LangGraph infrastructure.

Five subsystems:
  1. middleware — Composable cross-cutting concerns (NodeMiddleware chain)
  2. instrumented_graph — InstrumentedGraph subclass that wires the middleware chain
  3. tool_client — Transport-agnostic tool contracts (MCP-ready)
  4. node_validation — NodeResult envelope (used by middleware, not directly by nodes)
  5. llm — Protocol-based LLM interaction (CallLLM + stub + real backends)

This package has NO dependencies on domain models.
Only depends on: langgraph, langchain-core, pydantic.
"""

from conversation_engine.infrastructure.instrumented_graph import (
    InstrumentedGraph,
    # Legacy (deprecated) — use NodeMiddleware instead
    Interceptor,
    Middleware,
)
from conversation_engine.infrastructure.middleware import (
    NodeMiddleware,
    LoggingMiddleware,
    MetricsMiddleware,
    NodeMetrics,
    ValidationMiddleware,
    ErrorHandlingMiddleware,
    RetryMiddleware,
    CircuitBreakerMiddleware,
    ConfigMiddleware,
)
# Legacy interceptors (deprecated) — use middleware package instead
from conversation_engine.infrastructure.interceptors import (
    LoggingInterceptor,
    MetricsInterceptor,
    NodeMetrics as _LegacyNodeMetrics,
)
from conversation_engine.infrastructure.node_validation import (
    NodeError,
    NodeResult,
    validated_node,
    handle_error,
)
from conversation_engine.infrastructure.tool_client import (
    ToolSpec,
    ToolRegistry,
    ToolContentBlock,
    ToolResultEnvelope,
    ToolResultMeta,
    ToolClient,
    ToolCallError,
    LocalToolClient,
)
from conversation_engine.infrastructure.llm import (
    CallLLM,
    LLMRequest,
    LLMResponse,
    call_llm_stub,
)

__all__ = [
    # Instrumented graph
    "InstrumentedGraph",
    # Middleware (new — composable chain)
    "NodeMiddleware",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "NodeMetrics",
    "ValidationMiddleware",
    "ErrorHandlingMiddleware",
    "RetryMiddleware",
    "CircuitBreakerMiddleware",
    "ConfigMiddleware",
    # Legacy (deprecated)
    "Interceptor",
    "Middleware",
    "LoggingInterceptor",
    "MetricsInterceptor",
    # Node validation
    "NodeError",
    "NodeResult",
    "validated_node",
    "handle_error",
    # Tool client
    "ToolSpec",
    "ToolRegistry",
    "ToolContentBlock",
    "ToolResultEnvelope",
    "ToolResultMeta",
    "ToolClient",
    "ToolCallError",
    "LocalToolClient",
    # LLM
    "CallLLM",
    "LLMRequest",
    "LLMResponse",
    "call_llm_stub",
]
