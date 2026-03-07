"""
Creation Subgraph — the full creation pipeline as a nested graph.

This subgraph encapsulates: engine → fan-out → compile_voice ×N → assembler → presenter

KEY CONCEPTS:
  - The subgraph has its OWN state type (CreationState), not ParentState.
  - LangGraph maps parent ↔ child state by MATCHING FIELD NAMES.
  - When parent invokes the subgraph, overlapping fields are copied in.
  - When subgraph finishes, overlapping fields are copied back out.
  - The subgraph is INDEPENDENTLY TESTABLE — you can compile and invoke
    it on its own without the parent graph.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from ..state import CreationState


def mock_planner(state: CreationState) -> dict:
    """Return a fake plan based on user message."""
    msg = state.get("user_message", "").lower()

    if "jazz" in msg:
        return {
            "plan": {
                "genre": "Jazz",
                "key": "Bb Major",
                "tempo": 140,
                "sections": ["Head", "Solo", "Head"],
                "voices": ["Trumpet", "Sax", "Piano", "Bass"],
            }
        }

    return {
        "plan": {
            "genre": "Classical",
            "key": "C Major",
            "tempo": 120,
            "sections": ["Intro", "Main Theme", "Coda"],
            "voices": ["Violin", "Piano", "Cello"],
        }
    }


def compile_single_voice(state: CreationState) -> dict:
    """Compile a single voice (stub). Same pattern as M4."""
    voice = state["voice"]
    plan = state["plan"]

    result = {
        "voice": voice,
        "measures": 4,
        "notes": [f"{voice}_note_{i}" for i in range(4)],
        "tempo": plan.get("tempo", 120),
    }

    return {"voice_results": [result]}


def fan_out_voices(state: CreationState) -> list[Send]:
    """Routing function: spawn one compile_voice per voice in the plan."""
    plan = state["plan"]
    return [
        Send("compile_voice", {"voice": voice, "plan": plan})
        for voice in plan["voices"]
    ]


def assemble_all_voices(state: CreationState) -> dict:
    """Merge all voice results into a single assembled composition."""
    voice_results = state["voice_results"]

    assembled = {
        "voices": {vr["voice"]: vr for vr in voice_results},
        "total_voices": len(voice_results),
        "total_measures": sum(vr["measures"] for vr in voice_results),
    }

    return {"assembled": assembled}


def present_assembled_voices(state: CreationState) -> dict:
    """Format the final response for the user."""
    assembled = state["assembled"]
    plan = state["plan"]

    voice_names = ", ".join(assembled["voices"].keys())
    response = (
        f"Created a {plan['genre']} piece in {plan['key']} at {plan['tempo']} BPM. "
        f"Voices: {voice_names}. "
        f"Total measures: {assembled['total_measures']}."
    )

    return {"response": response}


def build_creation_subgraph():
    """Build the creation subgraph — independently compilable and testable.

    Graph:
      START → mock_planner → fan_out_voices → compile_voice ×N → assembler → presenter → END
    """
    builder = StateGraph(CreationState)

    builder.add_node("mock_planner", mock_planner)
    builder.add_node("compile_voice", compile_single_voice)
    builder.add_node("assembler", assemble_all_voices)
    builder.add_node("presenter", present_assembled_voices)

    builder.add_edge(START, "mock_planner")
    builder.add_conditional_edges("mock_planner", fan_out_voices)
    builder.add_edge("compile_voice", "assembler")
    builder.add_edge("assembler", "presenter")
    builder.add_edge("presenter", END)

    return builder.compile()
