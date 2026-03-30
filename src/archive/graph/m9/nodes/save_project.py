"""
Save Project node — M9: calls save_project tool via registry handler.
"""

from framework.langgraph_ext.tool_client.client import LocalToolClient

from ..state import ParentState


def make_save_project(tool_client: LocalToolClient):
    """Factory: save_project node backed by tool registry."""
    spec = tool_client._registry.get("save_project")

    def save_project(state: ParentState) -> dict:
        title = state.get("project_title", "Untitled Project")
        plan = state.get("plan")

        if plan is None:
            return {"response": "Nothing to save — no composition has been created yet."}

        validated = spec.input_model(
            title=title,
            sketch=state.get("sketch"),
            plan=plan,
            compile_result=state.get("compile_result"),
        )
        output = spec.handler(validated)
        return {
            "response": f"Saved '{output.title}' as version {output.version}.",
        }

    return save_project
