"""
Load Project node -- M12: direct store calls.
"""

from ..store import MusicStore
from ..state import ParentState


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
            "sketch": record.sketch, "plan": record.plan,
            "compile_result": record.compile_result,
            "response": f"Loaded '{record.title}' version {record.version} (saved {record.saved_at}).",
        }
    return load_project
