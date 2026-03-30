"""
Graph builder — M4: Fan-out / Fan-in.

The graph:
  START → mock_planner → fan_out_voices → compile_voice ×N → assembler → END

KEY CONCEPTS:
  - Send() dynamically spawns N parallel compile_voice nodes,
    one per voice in the plan. Each gets its own input dict.
  - The Annotated[list, operator.add] reducer on voice_results
    collects all parallel results into one list.
  - assembler runs AFTER all parallel nodes finish.
  - fan_out_voices is a ROUTING FUNCTION (not a node). It returns
    a list of Send() objects instead of a node name.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from .nodes import compile_voice, assembler
from .state import MusicGraphState


def mock_planner(state: MusicGraphState) -> dict:
    """Return a fake plan with voices to compile.
    Reused from M3 — in a real system this would be the real engine."""
    print("mock_planner")
    return {
        "plan": {
            "genre": "Classical",
            "key": "C Major",
            "tempo": 120,
            "sections": ["Intro", "Main Theme", "Coda"],
            "voices": ["Violin", "Piano", "Cello"],
        }
    }


def fan_out_voices(state: MusicGraphState) -> list[Send]:
    """Routing function: spawn one compile_voice per voice in the plan.

    This is NOT a node — it's used with add_conditional_edges.
    Instead of returning a single node name (like route_after_review in M3),
    it returns a LIST of Send() objects. Each Send() creates a parallel
    execution of compile_voice with its own input.

    Send("compile_voice", {...}) means:
      - Run the "compile_voice" node
      - With this specific input dict (not the full state)
    """
    plan = state["plan"]
    return [
        Send("compile_voice", {"voice": voice, "plan": plan})
        for voice in plan["voices"]
    ]


def build_music_graph():
    """Build the M4 graph with fan-out/fan-in parallel voice compilation."""
    builder = StateGraph(MusicGraphState)

    # Nodes
    builder.add_node("mock_planner", mock_planner)
    builder.add_node("compile_voice", compile_voice)
    builder.add_node("assembler", assembler)

    # Edges
    builder.add_edge(START, "mock_planner")

    # Fan-out: mock_planner → N parallel compile_voice nodes
    # fan_out_voices returns [Send("compile_voice", ...), Send("compile_voice", ...), ...]
    builder.add_conditional_edges("mock_planner", fan_out_voices)

    # Fan-in: all compile_voice nodes → assembler
    # LangGraph waits for ALL parallel nodes to finish before running assembler
    builder.add_edge("compile_voice", "assembler")

    builder.add_edge("assembler", END)

    return builder.compile()
