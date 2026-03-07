"""
Creation Subgraph — M10: InstrumentedGraph with interceptors.

KEY CONCEPT: Uses InstrumentedGraph instead of StateGraph. Every node
automatically gets interceptor hooks:
  - LoggingInterceptor: logs node entry/exit/timing
  - MetricsInterceptor: collects per-node call counts and durations

Nodes use the M9 pattern (registry handler direct calls) for real domain
objects. No StateMediator — just observability.

Pipeline (same as M8/M9):
  START → sketch_parser → engine → compiler → presenter → END
"""

from langgraph.graph import START, END

from framework.langgraph_ext.instrumented_graph import InstrumentedGraph
from framework.langgraph_ext.tool_client.client import LocalToolClient
from framework.langgraph_ext.tool_client.registry import ToolRegistry
from framework.langgraph_ext.interceptors.logging_interceptor import LoggingInterceptor
from framework.langgraph_ext.interceptors.metrics_interceptor import MetricsInterceptor

from ..state import CreationState


def _make_sketch_parser(registry: ToolRegistry):
    """Factory: sketch_parser node that calls parse_sketch via registry."""
    spec = registry.get("parse_sketch")

    def sketch_parser(state: CreationState) -> dict:
        validated = spec.input_model(user_message=state["user_message"])
        output = spec.handler(validated)
        return {"sketch": output.sketch}
    return sketch_parser


def _make_planner(registry: ToolRegistry):
    """Factory: engine node that calls plan_composition via registry."""
    spec = registry.get("plan_composition")

    def planner(state: CreationState) -> dict:
        validated = spec.input_model(sketch=state["sketch"])
        output = spec.handler(validated)
        return {"plan": output.plan}
    return planner


def _make_compiler(registry: ToolRegistry):
    """Factory: compiler node that calls compile_composition via registry."""
    spec = registry.get("compile_composition")

    def compiler(state: CreationState) -> dict:
        validated = spec.input_model(plan=state["plan"])
        output = spec.handler(validated)
        return {"compile_result": output.compile_result}
    return compiler


def _presenter(state: CreationState) -> dict:
    """Format a human-readable summary."""
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


def build_creation_subgraph(
    tool_client: LocalToolClient,
    logging_interceptor: LoggingInterceptor | None = None,
    metrics_interceptor: MetricsInterceptor | None = None,
):
    """Build the creation subgraph with InstrumentedGraph.

    Args:
        tool_client: LocalToolClient with registered tools.
        logging_interceptor: Optional shared LoggingInterceptor.
        metrics_interceptor: Optional shared MetricsInterceptor.
    """
    registry = tool_client._registry

    interceptors = []
    if logging_interceptor:
        interceptors.append(logging_interceptor)
    if metrics_interceptor:
        interceptors.append(metrics_interceptor)

    builder = InstrumentedGraph(
        CreationState,
        interceptors=interceptors,
    )

    builder.add_node("sketch_parser", _make_sketch_parser(registry))
    builder.add_node("engine", _make_planner(registry))
    builder.add_node("compiler", _make_compiler(registry))
    builder.add_node("presenter", _presenter)

    builder.add_edge(START, "sketch_parser")
    builder.add_edge("sketch_parser", "engine")
    builder.add_edge("engine", "compiler")
    builder.add_edge("compiler", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
