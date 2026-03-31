"""
Creation Subgraph — M7: Same as M6, real tools.

Pipeline:
  START → sketch_parser → engine → compiler → renderer → presenter → END

Identical to M6's creation subgraph — persistence is a parent concern.
"""

from langgraph.graph import StateGraph, START, END

from intent.sketch_models import Sketch
from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler

from ..state import CreationState


_planner = DeterministicPlanner()
_compiler = PatternCompiler()


def sketch_parser(state: CreationState) -> dict:
    """Parse user_message into a Sketch object."""
    sketch = Sketch(prompt=state["user_message"])
    return {"sketch": sketch}


def planner(state: CreationState) -> dict:
    """Run DeterministicPlanner: Sketch → PlanBundle."""
    sketch = state["sketch"]
    plan = _planner.plan(sketch)
    return {"plan": plan}


def compiler(state: CreationState) -> dict:
    """Run PatternCompiler: PlanBundle → CompileResult."""
    plan = state["plan"]
    result = _compiler.compile(plan)
    return {"compile_result": result}


def presenter(state: CreationState) -> dict:
    """Format a human-readable summary from plan and compile_result.

    Note: music21 Score is NOT rendered here — it's a presentation concern
    that happens outside the graph when needed (e.g. MIDI export, display).
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


def build_creation_subgraph():
    """Build the creation subgraph with real tools."""
    builder = StateGraph(CreationState)

    builder.add_node("sketch_parser", sketch_parser)
    builder.add_node("engine", planner)
    builder.add_node("compiler", compiler)
    builder.add_node("presenter", presenter)

    builder.add_edge(START, "sketch_parser")
    builder.add_edge("sketch_parser", "engine")
    builder.add_edge("engine", "compiler")
    builder.add_edge("compiler", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
