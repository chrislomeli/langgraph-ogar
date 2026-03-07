"""
Mock Planner — generates a fake plan for testing.

This node returns a dict that gets merged into state under the "plan" key.
The plan is just a plain dict — no schema yet. M6 replaces this with the
real DeterministicPlanner that produces a PlanBundle.
"""

from ..state import MusicGraphState


def mock_planner(state: MusicGraphState) -> dict:
    """Return a fake plan. The key insight: we return {"plan": {...}},
    and LangGraph merges that into state, so state["plan"] becomes the dict."""
    print("Mock Planner")
    if "funk" in state["user_message"]:
        return {
            "plan": {
                "genre": "Funk",
                "key": "E Minor",
                "tempo": 140,
                "sections": ["Intro", "Main Theme", "Break", "Outro"],
                "voices": ["Bass", "Drums", "Guitar", "Synth"],
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
