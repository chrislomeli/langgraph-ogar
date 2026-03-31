"""
State definitions — M6: Wire in the Real Tools.

M6 replaces mock data with real domain objects:
  - sketch: Sketch (Pydantic model from intent layer)
  - plan: PlanBundle (rich plan from DeterministicPlanner)
  - compile_result: CompileResult (composition IR from PatternCompiler)
  - score: music21 Score (rendered output)

KEY CONCEPT: The state now holds REAL domain objects, not dicts.
The graph structure is identical to M5 — only the node internals change.
"""

from __future__ import annotations

import operator
from typing import TypedDict, Optional, Annotated, Any
from enum import Enum


class IntentType(Enum):
    NEW_SKETCH = "new_sketch"
    REFINE_PLAN = "refine_plan"
    ANSWER_QUESTION = "answer_question"


class CreationState(TypedDict, total=False):
    """State for the creation subgraph — now with real domain objects."""

    user_message: str
    intent_type: Optional[IntentType]

    # Real domain objects (replacing mock dicts)
    sketch: Any           # intent.sketch_models.Sketch
    plan: Any             # intent.plan_models.PlanBundle
    compile_result: Any   # intent.compiler_interface.CompileResult
    score: Any            # music21.stream.Score
    response: str


class ParentState(TypedDict, total=False):
    """Parent graph state — routing + creation output."""

    # Routing
    user_message: str
    intent_type: Optional[IntentType]

    # Creation subgraph output (overlapping fields)
    sketch: Any
    plan: Any
    compile_result: Any
    score: Any
    response: str
