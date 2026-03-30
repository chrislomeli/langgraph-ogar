"""
Creation Subgraph — M9: Nodes call tools via ToolRegistry + LocalToolClient.

KEY CONCEPT: Instead of calling domain logic directly, nodes call tools
through the ToolRegistry. Each tool is a ToolSpec with Pydantic input/output
models and a handler. The LocalToolClient validates inputs/outputs and wraps
every result in a ToolResultEnvelope with provenance metadata.

The pipeline is identical to M8:
  START → sketch_parser → engine → compiler → presenter → END

But each node now:
  1. Looks up the ToolSpec from the registry
  2. Validates input through the Pydantic model
  3. Calls the handler to get real domain objects
  4. Also calls tool_client.call() to record provenance metadata

The tool_client is injected via a factory function (same HOF pattern as
make_save_project in M7/M8).
"""

from langgraph.graph import StateGraph, START, END

from framework.langgraph_ext.tool_client.client import LocalToolClient
from framework.langgraph_ext.tool_client.registry import ToolRegistry

from ..state import CreationState


def _make_sketch_parser(registry: ToolRegistry, tool_client: LocalToolClient):
    """Factory: sketch_parser node that calls parse_sketch tool."""
    spec = registry.get("parse_sketch")

    def sketch_parser(state: CreationState) -> dict:
        validated = spec.input_model(user_message=state["user_message"])
        output = spec.handler(validated)
        # Also record provenance via tool_client (fire-and-forget for metadata)
        tool_client.call("parse_sketch", {"user_message": state["user_message"]})
        return {"sketch": output.sketch}
    return sketch_parser


def _make_planner(registry: ToolRegistry, tool_client: LocalToolClient):
    """Factory: engine node that calls plan_composition tool."""
    spec = registry.get("plan_composition")

    def planner(state: CreationState) -> dict:
        validated = spec.input_model(sketch=state["sketch"])
        output = spec.handler(validated)
        return {"plan": output.plan}
    return planner


def _make_compiler(registry: ToolRegistry, tool_client: LocalToolClient):
    """Factory: compiler node that calls compile_composition tool."""
    spec = registry.get("compile_composition")

    def compiler(state: CreationState) -> dict:
        validated = spec.input_model(plan=state["plan"])
        output = spec.handler(validated)
        return {"compile_result": output.compile_result}
    return compiler


def _presenter(state: CreationState) -> dict:
    """Format a human-readable summary.

    The presenter doesn't need a tool — it's pure presentation logic.
    """
    plan = state["plan"]
    result = state["compile_result"]

    voice_names = ", ".join(v.name for v in plan.voice_plan.voices)
    track_count = len(result.composition.tracks)
    section_count = len(result.sections)

    response = (
        f"Created '{plan.title}' — {plan.key} at {plan.tempo_bpm} BPM.\n"
        f"Voices: {voice_names}\n"
        f"Form: {plan.form_plan.total_bars()} bars across "
        f"{len(plan.form_plan.sections)} sections.\n"
        f"Compiled: {track_count} tracks, {section_count} section versions."
    )

    return {"response": response}


def build_creation_subgraph(tool_client: LocalToolClient):
    """Build the creation subgraph with tool-backed nodes.

    Args:
        tool_client: LocalToolClient with registered tools.
    """
    registry = tool_client._registry
    builder = StateGraph(CreationState)

    builder.add_node("sketch_parser", _make_sketch_parser(registry, tool_client))
    builder.add_node("engine", _make_planner(registry, tool_client))
    builder.add_node("compiler", _make_compiler(registry, tool_client))
    builder.add_node("presenter", _presenter)

    builder.add_edge(START, "sketch_parser")
    builder.add_edge("sketch_parser", "engine")
    builder.add_edge("engine", "compiler")
    builder.add_edge("compiler", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
