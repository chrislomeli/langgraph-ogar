"""
Knowledge-graph tool — business-level CRD operations for the ReAct agent.

The LLM interacts with ``ProjectSnapshot`` (flat, name-based references).
It never sees nodes, edges, or IDs.  The tool handler converts snapshots
to/from the internal ``KnowledgeGraph`` via the snapshot facade, and
persists them through the ``ProjectStore``.

Methods:
    CREATE(payload)  — persist a new project from a ProjectSnapshot
    READ(key)        — retrieve an existing project as a ProjectSnapshot
    DELETE(key)      — remove a project by name

Update semantics: DELETE + CREATE (safe MVP approach).
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

from conversation_engine.infrastructure.tool_client.spec import ToolSpec
from conversation_engine.storage import ProjectStore
from conversation_engine.storage.snapshot import ProjectSnapshot
from conversation_engine.models.domain_config import DomainConfig
from conversation_engine.storage.snapshot_facade import (
    snapshot_to_graph,
    graph_to_snapshot,
    SnapshotConversionError,
)


# ── I/O models ─────────────────────────────────────────────────────
class CRUDMethod(str, Enum):
    CREATE = "CREATE"
    READ   = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ProjectGraphInput(BaseModel):
    """Input for the knowledge_graph tool."""
    method: CRUDMethod = Field(
        ...,
        description=(
            "The operation to perform: "
            "CREATE to persist a new project, "
            "READ to retrieve an existing project, "
            "DELETE to remove a project."
        ),
    )
    key: Optional[str] = Field(
        None,
        description=(
            "Project name — required for READ and DELETE. "
            "For CREATE, the project name is taken from the payload."
        ),
    )
    payload: Optional[ProjectSnapshot] = Field(
        None,
        description=(
            "The project data — required for CREATE. "
            "Omit for READ and DELETE."
        ),
    )


class ProjectGraphOutput(BaseModel):
    """Output from the knowledge_graph tool."""
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(default="", description="Human-readable status message")
    payload: Optional[ProjectSnapshot] = Field(
        None,
        description="The project data — returned by READ, None for CREATE and DELETE.",
    )


# ── CRUD operations ───────────────────────────────────────────────────

def _create_project(
    project_store: ProjectStore,
    snapshot: ProjectSnapshot,
) -> ProjectGraphOutput:
    """Create a new project from a snapshot."""
    if project_store.exists(snapshot.project_name):
        return ProjectGraphOutput(
            success=False,
            message=f"Project '{snapshot.project_name}' already exists. "
                    "DELETE it first, then CREATE again.",
        )
    try:
        graph = snapshot_to_graph(snapshot)
    except SnapshotConversionError as e:
        return ProjectGraphOutput(
            success=False,
            message=f"Invalid snapshot: {e}",
        )
    config = DomainConfig(
        project_name=snapshot.project_name,
        knowledge_graph=graph,
    )
    project_store.save(config)
    return ProjectGraphOutput(
        success=True,
        message=f"Project '{snapshot.project_name}' created "
                f"({graph.node_count()} nodes, {graph.edge_count()} edges).",
    )

def _update_project(
    project_store: ProjectStore,
    key: str,
    snapshot: ProjectSnapshot,
) -> ProjectGraphOutput:
    delete_result: ProjectGraphOutput = _delete_project(project_store, key)
    if not delete_result.success:
        return delete_result

    return _create_project(project_store, snapshot)


def _read_project(
    project_store: ProjectStore,
    key: str,
) -> ProjectGraphOutput:
    """Read an existing project as a snapshot."""
    config = project_store.load(key)
    if config is None:
        return ProjectGraphOutput(
            success=False,
            message=f"Project '{key}' not found.",
        )
    if config.knowledge_graph is None:
        return ProjectGraphOutput(
            success=True,
            message=f"Project '{key}' exists but has no knowledge graph.",
            payload=ProjectSnapshot(project_name=key),
        )
    snapshot = graph_to_snapshot(key, config.knowledge_graph)
    return ProjectGraphOutput(
        success=True,
        message=f"Project '{key}' loaded.",
        payload=snapshot,
    )


def _delete_project(
    project_store: ProjectStore,
    key: str,
) -> ProjectGraphOutput:
    """Delete a project by name."""
    removed = project_store.delete(key)
    if removed:
        return ProjectGraphOutput(
            success=True,
            message=f"Project '{key}' deleted.",
        )
    return ProjectGraphOutput(
        success=False,
        message=f"Project '{key}' not found.",
    )


# ── Tool factory ───────────────────────────────────────────────────

def make_project_graph_tool(project_store: ProjectStore) -> ToolSpec:
    """
    Create a knowledge_graph ToolSpec bound to a ProjectStore.

    Parameters
    ----------
    project_store : ProjectStore
        The persistence layer to use (InMemoryProjectStore,
        FileProjectStore, future MemgraphProjectStore, etc.)
    """

    def handler(input_: ProjectGraphInput) -> ProjectGraphOutput:
        match input_.method:
            case CRUDMethod.CREATE:
                if input_.payload is None:
                    return ProjectGraphOutput(
                        success=False,
                        message="CREATE requires a payload (ProjectSnapshot).",
                    )
                return _create_project(project_store, input_.payload)

            case CRUDMethod.UPDATE:
                if not input_.key:
                    return ProjectGraphOutput(
                        success=False,
                        message="UPDATE requires a key (project name).",
                    )
                if input_.payload is None:
                    return ProjectGraphOutput(
                        success=False,
                        message="UPDATE requires a payload (ProjectSnapshot).",
                    )
                return _update_project(project_store, input_.key, input_.payload)

            case CRUDMethod.READ:
                if not input_.key:
                    return ProjectGraphOutput(
                        success=False,
                        message="READ requires a key (project name).",
                    )
                return _read_project(project_store, input_.key)

            case CRUDMethod.DELETE:
                if not input_.key:
                    return ProjectGraphOutput(
                        success=False,
                        message="DELETE requires a key (project name).",
                    )
                return _delete_project(project_store, input_.key)

            case _:
                return ProjectGraphOutput(
                    success=False,
                    message=f"Unknown method '{input_.method}'. Use CREATE, READ, or DELETE.",
                )




    return ToolSpec(
        name="knowledge_graph",
        description=(
            "Perform business-level operations on a project's knowledge graph. "
            "This is the sole interface for persisting and retrieving project data.\n\n"
            "Methods:\n"
            "  CREATE(payload) — persist a new project from a ProjectSnapshot\n"
            "  READ(key)       — retrieve an existing project as a ProjectSnapshot\n"
            "  DELETE(key)     — remove a project by name\n\n"
            "To update a project, DELETE it first then CREATE with the new data.\n\n"
            "The payload is a ProjectSnapshot with goals, requirements, capabilities, "
            "components, constraints, and dependencies. Use name-based references "
            "(e.g. a requirement's goal_ref is the goal's name, not an ID)."
        ),
        input_model=ProjectGraphInput,
        output_model=ProjectGraphOutput,
        handler=handler,
    )
