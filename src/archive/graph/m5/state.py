"""
State definitions — M5: Subgraphs.

M5 introduces TWO state types:
  - CreationState: Internal state for the creation subgraph.
    Only contains fields the creation pipeline needs.
  - ParentState: The parent graph's state, which includes
    routing fields AND the creation subgraph's output.

KEY CONCEPT: The subgraph has its own state type that's a SUBSET
of the parent state. Overlapping field names are how LangGraph
passes data between parent and child. When the parent invokes
the subgraph, it copies matching fields in. When the subgraph
finishes, it copies matching fields back out.
"""

from __future__ import annotations

import operator
from typing import TypedDict, Optional, Annotated
from enum import Enum


class IntentType(Enum):
    NEW_SKETCH = "new_sketch"
    REFINE_PLAN = "refine_plan"
    ANSWER_QUESTION = "answer_question"


class CreationState(TypedDict, total=False):
    """State for the creation subgraph only.
    This is a SUBSET of ParentState — only the fields creation needs."""

    user_message: str
    intent_type: Optional[IntentType]
    plan: Optional[dict]
    voice_results: Annotated[list[dict], operator.add]
    assembled: Optional[dict]
    response: str


class ParentState(TypedDict, total=False):
    """State for the parent graph. Includes routing + creation output."""

    # Routing fields
    user_message: str
    intent_type: Optional[IntentType]

    # Creation subgraph output (overlapping field names)
    plan: Optional[dict]
    voice_results: Annotated[list[dict], operator.add]
    assembled: Optional[dict]
    response: str
