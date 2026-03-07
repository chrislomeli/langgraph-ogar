"""
Save Project node -- M12: direct store calls.
"""

from ..store import MusicStore
from ..state import ParentState


def make_save_project(store: MusicStore):
    def save_project(state: ParentState) -> dict:
        title = state.get("project_title", "Untitled Project")
        plan = state.get("plan")
        if plan is None:
            return {"response": "Nothing to save -- no composition has been created yet."}
        record = store.save(
            title=title, sketch=state.get("sketch"),
            plan=plan, compile_result=state.get("compile_result"),
        )
        return {"response": f"Saved '{record.title}' as version {record.version}."}
    return save_project
