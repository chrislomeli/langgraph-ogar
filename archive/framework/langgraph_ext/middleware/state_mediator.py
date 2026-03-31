"""
StateMediator -- Middleware that routes tool results to state update handlers.

The mediator inspects the ToolResultEnvelope metadata (tool_name) embedded
in the node's return value and dispatches to a registered handler that
knows how to translate that tool's output into a state patch.

Usage:
    mediator = StateMediator()
    mediator.register("compile_pattern", handler=merge_compilation_result)
    mediator.register("plan_voices", handler=extract_voice_plans)

    graph = InstrumentedGraph(MyState, middleware=[mediator])

Each handler is a pure function:
    (node_name, current_state, envelope) -> state_patch_dict

If no handler is registered for a tool, the result passes through unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Protocol

from framework.langgraph_ext.instrumented_graph import Middleware
from framework.langgraph_ext.tool_client.envelope import ToolResultEnvelope

logger = logging.getLogger(__name__)


class MediatorHandler(Protocol):
    """Signature for state mediation handlers."""

    def __call__(
        self,
        node_name: str,
        state: Any,
        envelope: ToolResultEnvelope,
    ) -> dict[str, Any]:
        """
        Translate a tool result envelope into a state patch.

        Args:
            node_name: The graph node that produced this result.
            state: Current graph state (read-only by convention).
            envelope: The tool result with metadata.

        Returns:
            A dict of state fields to update.
        """
        ...


class StateMediator(Middleware):
    """
    Middleware that routes tool results to state-update handlers
    based on the tool_name in the ToolResultEnvelope metadata.

    If the node result contains a ToolResultEnvelope (or a dict with
    '_meta.tool_name'), the mediator looks up a handler and produces
    a state patch. Otherwise, the result passes through unchanged.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, MediatorHandler] = {}

    def register(
        self,
        tool_name: str,
        handler: MediatorHandler,
    ) -> None:
        """Register a handler for a specific tool name."""
        if tool_name in self._handlers:
            raise ValueError(f"Handler already registered for tool '{tool_name}'")
        self._handlers[tool_name] = handler

    def registered_tools(self) -> list[str]:
        """Return sorted list of tool names with registered handlers."""
        return sorted(self._handlers.keys())

    def transform(self, node_name: str, state: Any, result: Any) -> Any:
        """
        If result contains tool envelope metadata, route to the
        appropriate handler. Otherwise, pass through unchanged.
        """
        envelope = self._extract_envelope(result)
        if envelope is None:
            return result

        tool_name = envelope.meta.tool_name
        handler = self._handlers.get(tool_name)

        if handler is None:
            logger.debug(
                "[StateMediator] No handler for tool '%s' in node '%s', passing through",
                tool_name,
                node_name,
            )
            return result

        logger.debug(
            "[StateMediator] Routing tool '%s' from node '%s' to handler",
            tool_name,
            node_name,
        )
        return handler(node_name, state, envelope)

    @staticmethod
    def _extract_envelope(result: Any) -> ToolResultEnvelope | None:
        """Try to extract a ToolResultEnvelope from the node result."""
        if isinstance(result, ToolResultEnvelope):
            return result

        if isinstance(result, dict) and "_meta" in result:
            try:
                from framework.langgraph_ext.tool_client.envelope import ToolResultMeta
                meta = ToolResultMeta(**result["_meta"])
                structured = {k: v for k, v in result.items() if k != "_meta"}
                return ToolResultEnvelope(meta=meta, structured=structured)
            except Exception:
                return None

        return None
