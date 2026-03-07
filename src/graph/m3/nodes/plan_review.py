"""
Plan Review — human-in-the-loop checkpoint.

interrupt() pauses the graph and waits for the human to resume.
  - Its argument is what the human SEES  (the plan)
  - Its return value is what the human SENDS BACK  (approved or not)
"""

from langgraph.types import interrupt
from ..state import MusicGraphState

#
def auto_approve(plan: dict) -> dict:
    """Simple tool that always approves. Use for non-interactive pipelines."""
    return {"approved": True}


def plan_review(state: MusicGraphState) -> dict:
    """Pause for human review, then put their decision into state."""
    human_response = interrupt({"plan": state["plan"]})
    return {"approved": human_response["approved"]}
