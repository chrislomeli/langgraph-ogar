"""
State definitions — M8: The Refinement Loop.

M8 adds a RefinementState for the refinement subgraph:
  - refinement_prompt: what the user wants to change
  - previous_plan: the plan before refinement
  - previous_compile_result: the compilation before refinement
  - changed_voice_ids: which voices need recompilation

KEY CONCEPT: The refinement subgraph takes a PREVIOUS result
and produces a NEW result by only recompiling what changed.
This is a CYCLE — the user can refine repeatedly.
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
    """State for the creation subgraph — same as M7."""

    user_message: str
    intent_type: Optional[IntentType]

    sketch: Any           # intent.sketch_models.Sketch
    plan: Any             # intent.plan_models.PlanBundle
    compile_result: Any   # intent.compiler_interface.CompileResult
    response: str


class RefinementState(TypedDict, total=False):
    """State for the refinement subgraph.

    The refinement subgraph needs both the current state AND
    the previous state to do scoped recompilation.
    """

    user_message: str
    intent_type: Optional[IntentType]

    # Current artifacts (will be updated by refinement)
    plan: Any             # PlanBundle — refined plan
    compile_result: Any   # CompileResult — recompiled result

    # Refinement-specific fields
    previous_plan: Any           # PlanBundle before refinement
    previous_compile_result: Any # CompileResult before refinement
    changed_voice_ids: Optional[set]  # Which voices need recompilation

    response: str


class ParentState(TypedDict, total=False):
    """Parent graph state — routing + creation + refinement + persistence."""

    # Routing
    user_message: str
    intent_type: Optional[IntentType]

    # Creation/refinement output (overlapping fields)
    sketch: Any
    plan: Any
    compile_result: Any
    response: str

    # Refinement-specific (overlapping with RefinementState)
    previous_plan: Any
    previous_compile_result: Any
    changed_voice_ids: Optional[set]

    # Persistence fields (from M7)
    project_title: Optional[str]
    project_version: Optional[int]
    project_record: Any
