"""
Assembler — fan-in collector node.

Runs AFTER all compile_voice nodes have finished. By the time this
node executes, voice_results contains one entry per voice (thanks
to the Annotated[list, operator.add] reducer).

The assembler's job: take all the individual voice results and
merge them into a single assembled composition.

In M6 this gets replaced with real assembly logic that builds
a CompileResult from individual voice sections.
"""

from ..state import MusicGraphState


def assembler(state: MusicGraphState) -> dict:
    """Merge all voice results into a single assembled composition."""
    voice_results = state["voice_results"]

    assembled = {
        "voices": {vr["voice"]: vr for vr in voice_results},
        "total_voices": len(voice_results),
        "total_measures": sum(vr["measures"] for vr in voice_results),
    }

    return {"assembled": assembled}
