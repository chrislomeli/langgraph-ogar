"""
State definitions — M9: ToolSpec + Registry.

Same state as M8 — no state changes in this milestone.
The innovation is in HOW nodes populate state (via tool client),
not WHAT state fields exist.
"""

from __future__ import annotations

from typing import TypedDict, Optional, Any
from enum import Enum


class IntentType(Enum):
    NEW_SKETCH = "new_sketch"
    REFINE_PLAN = "refine_plan"
    SAVE_PROJECT = "save_project"
    LOAD_PROJECT = "load_project"
    LIST_PROJECTS = "list_projects"
    ANSWER_QUESTION = "answer_question"


class CreationState(TypedDict, total=False):
    """State for the creation subgraph."""

    user_message: str
    intent_type: Optional[IntentType]

    sketch: Any           # intent.sketch_models.Sketch
    plan: Any             # intent.plan_models.PlanBundle
    compile_result: Any   # intent.compiler_interface.CompileResult
    response: str


class RefinementState(TypedDict, total=False):
    """State for the refinement subgraph."""

    user_message: str
    intent_type: Optional[IntentType]

    plan: Any
    compile_result: Any

    previous_plan: Any
    previous_compile_result: Any
    changed_voice_ids: Optional[set]

    response: str


class ParentState(TypedDict, total=False):
    """Parent graph state — routing + creation + refinement + persistence."""

    # Routing
    user_message: str
    intent_type: Optional[IntentType]

    # Creation/refinement output
    sketch: Any
    plan: Any
    compile_result: Any
    response: str

    # Refinement-specific
    previous_plan: Any
    previous_compile_result: Any
    changed_voice_ids: Optional[set]

    # Persistence fields
    project_title: Optional[str]
    project_version: Optional[int]
    project_record: Any
