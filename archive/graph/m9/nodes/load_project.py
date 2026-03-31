"""
Load Project node — M9: calls load_project tool via registry handler.

Uses the handler directly (not tool_client.call) so that domain objects
(Sketch, PlanBundle, CompileResult) come back as real Python objects
rather than serialized dicts.
"""

from framework.langgraph_ext.tool_client.client import LocalToolClient

from ..state import ParentState


def make_load_project(tool_client: LocalToolClient):
    """Factory: load_project node backed by tool registry."""
    spec = tool_client._registry.get("load_project")

    def load_project(state: ParentState) -> dict:
        title = state.get("project_title", "")
        if not title:
            return {"response": "No project title specified."}

        version = state.get("project_version")
        try:
            validated = spec.input_model(title=title, version=version)
            output = spec.handler(validated)
        except KeyError as e:
            return {"response": str(e)}

        return {
            "sketch": output.sketch,
            "plan": output.plan,
            "compile_result": output.compile_result,
            "response": f"Loaded '{output.title}' version {output.version} (saved {output.saved_at}).",
        }

    return load_project
