"""
State definitions — M7: Persistence — Save and Load.

Builds on M6 state, adding:
  - project_title: Name for saving/loading projects
  - project_version: Specific version to load (optional)
  - project_record: The loaded/saved ProjectRecord

The creation subgraph state is identical to M6.
New fields are only in ParentState since persistence
is a parent-level concern.
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
    """State for the creation subgraph.

    Note: music21 Score is NOT stored in state — it's rendered on demand
    from compile_result when needed for presentation.
    """

    user_message: str
    intent_type: Optional[IntentType]

    sketch: Any           # intent.sketch_models.Sketch
    plan: Any             # intent.plan_models.PlanBundle
    compile_result: Any   # intent.compiler_interface.CompileResult
    response: str


class ParentState(TypedDict, total=False):
    """Parent graph state — routing + creation + persistence."""

    # Routing
    user_message: str
    intent_type: Optional[IntentType]

    # Creation subgraph output (overlapping fields)
    sketch: Any
    plan: Any
    compile_result: Any
    response: str

    # Persistence fields (parent-only)
    project_title: Optional[str]
    project_version: Optional[int]
    project_record: Any   # store.ProjectRecord
