"""
Compile Voice — fan-out target node.

Each instance receives a SINGLE voice to compile (not the full state).
Send() creates one instance per voice in the plan, each with its own
input dict containing the voice name and the plan.

KEY CONCEPT: This node receives a custom input dict from Send(),
not the full graph state. It returns a partial dict that the
Annotated reducer merges into voice_results.

In M6 this gets replaced with the real PatternCompiler.
"""

from ..state import MusicGraphState


def compile_voice(state: MusicGraphState) -> dict:
    """Compile a single voice. Returns a result that gets appended to voice_results.

    Send() provides state with 'voice' (str) and 'plan' (dict).
    We return a list with one item — the reducer (operator.add) will
    concatenate all the lists from parallel nodes into one flat list.
    """
    voice = state["voice"]
    plan = state["plan"]

    # Stub: generate fake compiled data for this voice
    result = {
        "voice": voice,
        "measures": 4,
        "notes": [f"{voice}_note_{i}" for i in range(4)],
        "tempo": plan.get("tempo", 120),
    }

    # Return as a list — operator.add will concatenate all results
    return {"voice_results": [result]}
