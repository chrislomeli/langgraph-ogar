"""
Creation Subgraph — M6: Real tools replacing stubs.

The pipeline:
  START → sketch_parser → engine → compiler → renderer → presenter → END

KEY CONCEPT: The graph structure is the same as M5's creation subgraph.
The only difference is that nodes now call REAL implementations:
  - sketch_parser: Constructs a Sketch from user_message
  - engine: DeterministicPlanner.plan(sketch) → PlanBundle
  - compiler: PatternCompiler.compile(plan) → CompileResult
  - renderer: render_composition() → music21 Score
  - presenter: Formats a human-readable summary

No fan-out in M6 — the PatternCompiler handles ALL voices internally.
This is different from M4/M5 where we had per-voice fan-out with stubs.
The real compiler is a single call that produces the complete composition.
"""

from langgraph.graph import StateGraph, START, END

from intent.sketch_models import Sketch
from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler
from symbolic_music.rendering import render_composition

from ..state import CreationState


# Instantiate the real tools once
_planner = DeterministicPlanner()
_compiler = PatternCompiler()


def sketch_parser(state: CreationState) -> dict:
    """Parse user_message into a Sketch object.

    In production, this would be an LLM call with structured output
    that extracts genre, key, tempo, voice hints, etc. from natural language.
    For M6, we construct a Sketch directly from the prompt string.
    The DeterministicPlanner will infer genre, key, tempo, etc. from the prompt.
    """
    sketch = Sketch(prompt=state["user_message"])
    return {"sketch": sketch}


def planner(state: CreationState) -> dict:
    """Run DeterministicPlanner: Sketch → PlanBundle.

    The engine reads the sketch prompt and produces a complete PlanBundle
    with voice roster, form structure, harmony, groove, and render settings.
    """
    sketch = state["sketch"]
    plan = _planner.plan(sketch)
    return {"plan": plan}


def compiler(state: CreationState) -> dict:
    """Run PatternCompiler: PlanBundle → CompileResult.

    The compiler generates per-voice SectionSpecs for each section,
    assembles TrackSpecs, and builds the CompositionSpec with
    MeterMap and TempoMap. This is a single call — the compiler
    handles all voices internally (unlike the M4 per-voice fan-out).
    """
    plan = state["plan"]
    result = _compiler.compile(plan)
    return {"compile_result": result}


def renderer(state: CreationState) -> dict:
    """Run render_composition: CompositionSpec → music21 Score.

    Converts the domain IR into a music21 Score that can be
    played, exported to MIDI/MusicXML, or displayed.
    """
    result = state["compile_result"]
    score = render_composition(result.composition, result.sections)
    return {"score": score}


def presenter(state: CreationState) -> dict:
    """Format a human-readable summary of the created composition."""
    plan = state["plan"]
    result = state["compile_result"]
    score = state["score"]

    voice_names = ", ".join(v.name for v in plan.voice_plan.voices)
    track_count = len(result.composition.tracks)
    section_count = len(result.sections)
    part_count = len(score.parts)

    response = (
        f"Created '{plan.title}' — {plan.key} at {plan.tempo_bpm} BPM.\n"
        f"Voices: {voice_names}\n"
        f"Form: {plan.form_plan.total_bars()} bars across "
        f"{len(plan.form_plan.sections)} sections.\n"
        f"Compiled: {track_count} tracks, {section_count} section versions.\n"
        f"Rendered: {part_count} parts in music21 Score."
    )

    return {"response": response}


def build_creation_subgraph():
    """Build the creation subgraph with real tools.

    Graph:
      START → sketch_parser → engine → compiler → renderer → presenter → END
    """
    builder = StateGraph(CreationState)

    builder.add_node("sketch_parser", sketch_parser)
    builder.add_node("engine", planner)
    builder.add_node("compiler", compiler)
    builder.add_node("renderer", renderer)
    builder.add_node("presenter", presenter)

    builder.add_edge(START, "sketch_parser")
    builder.add_edge("sketch_parser", "engine")
    builder.add_edge("engine", "compiler")
    builder.add_edge("compiler", "renderer")
    builder.add_edge("renderer", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
