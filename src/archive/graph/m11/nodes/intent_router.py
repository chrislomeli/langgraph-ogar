"""
Intent Router -- same as M10 (keyword-based routing).
"""

import re
from ..state import ParentState, IntentType


def intent_router(state: ParentState) -> dict:
    """Classify user message and prepare state for routing."""
    msg = state["user_message"].lower()

    if any(kw in msg for kw in ["save", "store"]):
        title = _extract_title(state["user_message"], "save")
        return {
            "intent_type": IntentType.SAVE_PROJECT,
            "project_title": title,
        }
    elif any(kw in msg for kw in ["load", "open", "resume"]):
        title = _extract_title(state["user_message"], "load")
        return {
            "intent_type": IntentType.LOAD_PROJECT,
            "project_title": title,
        }
    elif any(kw in msg for kw in ["list", "show projects", "my projects"]):
        return {"intent_type": IntentType.LIST_PROJECTS}
    elif any(kw in msg for kw in ["refine", "change", "make the", "modify", "add a", "remove the"]):
        update = {"intent_type": IntentType.REFINE_PLAN}
        if state.get("plan") is not None:
            update["previous_plan"] = state["plan"]
        if state.get("compile_result") is not None:
            update["previous_compile_result"] = state["compile_result"]
        return update
    elif any(kw in msg for kw in ["write", "create", "compose", "new"]):
        return {"intent_type": IntentType.NEW_SKETCH}
    else:
        return {"intent_type": IntentType.ANSWER_QUESTION}


def _extract_title(msg: str, verb: str) -> str:
    match = re.search(rf'{verb}\s+as\s+"?([^"]+)"?', msg, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(rf'{verb}\s+"?([^"]+)"?', msg, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "Untitled Project"


def route_by_intent(state: ParentState) -> str:
    intent = state.get("intent_type")
    routes = {
        IntentType.NEW_SKETCH: "creation",
        IntentType.REFINE_PLAN: "refinement",
        IntentType.SAVE_PROJECT: "save_project",
        IntentType.LOAD_PROJECT: "load_project",
        IntentType.LIST_PROJECTS: "list_projects",
        IntentType.ANSWER_QUESTION: "answerer",
    }
    return routes.get(intent, "answerer")
