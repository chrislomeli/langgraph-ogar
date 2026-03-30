"""
State definitions -- M12: Prompt Templates + LLM Swap.

Same state as M11 plus a strategy_used field to track which
engine strategy was used (deterministic vs LLM).
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
    user_message: str
    intent_type: Optional[IntentType]
    sketch: Any
    plan: Any
    compile_result: Any
    response: str
    plan_graph: Any
    orchestrator_events: list
    strategy_used: str   # "deterministic" or "llm"


class RefinementState(TypedDict, total=False):
    user_message: str
    intent_type: Optional[IntentType]
    plan: Any
    compile_result: Any
    previous_plan: Any
    previous_compile_result: Any
    changed_voice_ids: Optional[set]
    response: str
    plan_graph: Any
    orchestrator_events: list
    strategy_used: str


class ParentState(TypedDict, total=False):
    user_message: str
    intent_type: Optional[IntentType]
    sketch: Any
    plan: Any
    compile_result: Any
    response: str
    previous_plan: Any
    previous_compile_result: Any
    changed_voice_ids: Optional[set]
    project_title: Optional[str]
    project_version: Optional[int]
    project_record: Any
    plan_graph: Any
    orchestrator_events: list
    strategy_used: str
