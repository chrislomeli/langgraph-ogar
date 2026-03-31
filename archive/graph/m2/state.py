"""
MusicGraphState — the state that flows through the entire graph.

This is a TypedDict. Every node receives the full state and returns
a partial dict of updates. LangGraph merges the updates automatically.

Milestone 1 starts with a minimal set of fields.
Future milestones add fields as needed (intent_type, plan, voices, etc.).
"""

from __future__ import annotations

from typing import TypedDict, Optional

from enum import Enum

class IntentType(Enum):
    NEW_SKETCH = 1
    REFINE_PLAN = 2
    SAVE_PROJECT = 3
    SAVE_REQUESTS = 4
    LOAD_REQUESTS = 5
    ANSWER_QUESTION = 6




class MusicGraphState(TypedDict, total=False):
    """
    Graph state for the symbolic music agent.

    M1 fields:
        user_message: The raw user input string.
        summary: A processed summary (set by a processing node).
        response: The final formatted response (set by presenter).

    M2 fields:
        intent_type: The classified intent (set by intent_router).
    """
    user_message: str
    summary: str
    response: str
    intent_type: IntentType
    path: str
