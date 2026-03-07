"""
Load Project node — restores artifacts from the store into state.

KEY CONCEPT: Loading a project hydrates the graph state with previously
saved artifacts. After loading, the user can continue refining (M8)
or re-render without re-running the full pipeline.
"""

from ..state import ParentState
from ..store import MusicStore


def make_load_project(store: MusicStore):
    """Factory: creates a load_project node with the store injected."""

    def load_project(state: ParentState) -> dict:
        """Load a project from the store into state."""
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
            "response": (
                f"Loaded '{record.title}' version {record.version} "
                f"(saved {record.saved_at})."
            ),
        }

    return load_project
