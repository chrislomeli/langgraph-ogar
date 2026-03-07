"""
List Projects node — shows all saved projects.
"""

from ..state import ParentState
from ..store import MusicStore


def make_list_projects(store: MusicStore):
    """Factory: creates a list_projects node with the store injected."""

    def list_projects(state: ParentState) -> dict:
        """List all saved projects."""
        projects = store.list_projects()

        if not projects:
            return {"response": "No saved projects yet."}

        lines = [f"Saved projects ({len(projects)}):"]
        for p in projects:
            lines.append(
                f"  - '{p['title']}' — {p['versions']} version(s), "
                f"last saved {p['saved_at']}"
            )

        return {"response": "\n".join(lines)}

    return list_projects
