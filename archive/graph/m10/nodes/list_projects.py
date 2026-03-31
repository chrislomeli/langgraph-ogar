"""
List Projects node — M10: calls tool via registry handler.
"""

from framework.langgraph_ext.tool_client.client import LocalToolClient

from ..state import ParentState


def make_list_projects(tool_client: LocalToolClient):
    """Factory: list_projects node backed by tool registry."""
    spec = tool_client._registry.get("list_projects")

    def list_projects(state: ParentState) -> dict:
        validated = spec.input_model()
        output = spec.handler(validated)
        projects = output.projects

        if not projects:
            return {"response": "No saved projects yet."}

        lines = [f"Saved projects ({len(projects)}):"]
        for p in projects:
            lines.append(f"  - '{p['title']}' — {p['versions']} version(s), last saved {p['saved_at']}")
        return {"response": "\n".join(lines)}

    return list_projects
