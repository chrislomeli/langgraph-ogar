"""
Load Project node — same factory pattern as M7.
"""

from ..state import ParentState
from ..store import MusicStore


def make_load_project(store: MusicStore):
    def load_project(state: ParentState) -> dict:
        title = state.get("project_title", "")
        if not title:
            return {"response": "No project title specified."}

        version = state.get("project_version")
        try:
            record = store.load(title, version=version)
        except KeyError as e:
            return {"response": str(e)}

        return {
            "project_record": record,
            "sketch": record.sketch,
            "plan": record.plan,
            "compile_result": record.compile_result,
            "response": f"Loaded '{record.title}' version {record.version} (saved {record.saved_at}).",
        }

    return load_project
