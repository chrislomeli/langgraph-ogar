"""
MusicGraphState — M4: Fan-out / Fan-in.

M4 adds:
- voice_results: Annotated list with operator.add reducer.
  Each compile_voice node appends its result; LangGraph merges them.
- assembled: The final merged result from the assembler node.

KEY CONCEPT: The Annotated[list, operator.add] reducer is what makes
fan-in work. Without it, each parallel node would overwrite the list
instead of appending to it.
"""

from __future__ import annotations

import operator
from typing import TypedDict, Optional, Annotated

from enum import Enum


class IntentType(Enum):
    NEW_SKETCH = 1
    REFINE_PLAN = 2
    SAVE_PROJECT = 3
    SAVE_REQUESTS = 4
    LOAD_REQUESTS = 5
    ANSWER_QUESTION = 6


class MusicGraphState(TypedDict, total=False):
    """State that flows through the graph. M4 extends with fan-out/fan-in fields."""

    # M1 fields
    user_message: str
    intent_type: IntentType
    response: str

    # M3 fields
    plan: Optional[dict]
    approved: Optional[bool]

    # M4 fields
    voice_results: Annotated[list[dict], operator.add]  # Fan-in reducer
    assembled: Optional[dict]  # Final merged result from assembler
