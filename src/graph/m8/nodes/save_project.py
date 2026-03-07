"""
Save Project node — same factory pattern as M7.
"""

from ..state import ParentState
from ..store import MusicStore


def make_save_project(store: MusicStore):
    def save_project(state: ParentState) -> dict:
        title = state.get("project_title", "Untitled Project")
        sketch = state.get("sketch")
        plan = state.get("plan")
        compile_result = state.get("compile_result")

        if plan is None:
            return {"response": "Nothing to save — no composition has been created yet."}

        record = store.save(title=title, sketch=sketch, plan=plan, compile_result=compile_result)
        return {
            "project_record": record,
            "response": f"Saved '{record.title}' as version {record.version}.",
        }

    return save_project
