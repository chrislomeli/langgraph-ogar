"""
Save Project node — persists the current creation artifacts.

KEY CONCEPT: The node receives the store via closure (dependency injection).
It doesn't know or care whether the store is InMemoryStore or MemgraphStore.
The make_save_project() factory creates the node function with the store bound.
"""

from ..state import ParentState
from ..store import MusicStore


def make_save_project(store: MusicStore):
    """Factory: creates a save_project node with the store injected."""

    def save_project(state: ParentState) -> dict:
        """Save the current project artifacts to the store."""
        title = state.get("project_title", "Untitled Project")
        sketch = state.get("sketch")
        plan = state.get("plan")
        compile_result = state.get("compile_result")

        if plan is None:
            return {"response": f"Nothing to save — no composition has been created yet."}

        record = store.save(
            title=title,
            sketch=sketch,
            plan=plan,
            compile_result=compile_result,
        )

        return {
            "project_record": record,
            "response": (
                f"Saved '{record.title}' as version {record.version}."
            ),
        }

    return save_project
