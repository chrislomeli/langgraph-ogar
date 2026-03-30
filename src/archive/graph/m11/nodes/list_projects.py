"""
List Projects node -- M11: direct store calls.
"""

from ..store import MusicStore
from ..state import ParentState


def make_list_projects(store: MusicStore):
    """Factory: list_projects node."""
    def list_projects(state: ParentState) -> dict:
        projects = store.list_projects()
        if not projects:
            return {"response": "No saved projects yet."}
        lines = [f"Saved projects ({len(projects)}):"]
        for p in projects:
            lines.append(f"  - '{p['title']}' -- {p['versions']} version(s), last saved {p['saved_at']}")
        return {"response": "\n".join(lines)}

    return list_projects
