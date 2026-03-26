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

from typing import Literal, Optional

from pydantic import BaseModel, Field

from conversation_engine.infrastructure.tool_client.spec import ToolSpec
from conversation_engine.storage.snapshot import ProjectSnapshot


# ── I/O models ─────────────────────────────────────────────────────

class KnowledgeGraphInput(BaseModel):
    """Input for the knowledge_graph tool."""
    method: Literal["CREATE", "READ", "DELETE"] = Field(
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


class KnowledgeGraphOutput(BaseModel):
    """Output from the knowledge_graph tool."""
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(default="", description="Human-readable status message")
    payload: Optional[ProjectSnapshot] = Field(
        None,
        description="The project data — returned by READ, None for CREATE and DELETE.",
    )


# ── Tool factory ───────────────────────────────────────────────────

def make_knowledge_graph_tool(project_store) -> ToolSpec:
    """
    Create a knowledge_graph ToolSpec bound to a ProjectStore.

    Parameters
    ----------
    project_store : ProjectStore
        The persistence layer to use (InMemoryProjectStore,
        FileProjectStore, future MemgraphProjectStore, etc.)
    """
    from conversation_engine.models.domain_config import DomainConfig
    from conversation_engine.storage.snapshot_facade import (
        snapshot_to_graph,
        graph_to_snapshot,
        SnapshotConversionError,
    )

    def handler(input_: KnowledgeGraphInput) -> KnowledgeGraphOutput:
        match input_.method:

            case "CREATE":
                if input_.payload is None:
                    return KnowledgeGraphOutput(
                        success=False,
                        message="CREATE requires a payload (ProjectSnapshot).",
                    )
                snapshot = input_.payload
                if project_store.exists(snapshot.project_name):
                    return KnowledgeGraphOutput(
                        success=False,
                        message=f"Project '{snapshot.project_name}' already exists. "
                                "DELETE it first, then CREATE again.",
                    )
                try:
                    graph = snapshot_to_graph(snapshot)
                except SnapshotConversionError as e:
                    return KnowledgeGraphOutput(
                        success=False,
                        message=f"Invalid snapshot: {e}",
                    )
                config = DomainConfig(
                    project_name=snapshot.project_name,
                    knowledge_graph=graph,
                )
                project_store.save(config)
                return KnowledgeGraphOutput(
                    success=True,
                    message=f"Project '{snapshot.project_name}' created "
                            f"({graph.node_count()} nodes, {graph.edge_count()} edges).",
                )

            case "READ":
                key = input_.key
                if not key:
                    return KnowledgeGraphOutput(
                        success=False,
                        message="READ requires a key (project name).",
                    )
                config = project_store.load(key)
                if config is None:
                    return KnowledgeGraphOutput(
                        success=False,
                        message=f"Project '{key}' not found.",
                    )
                if config.knowledge_graph is None:
                    return KnowledgeGraphOutput(
                        success=True,
                        message=f"Project '{key}' exists but has no knowledge graph.",
                        payload=ProjectSnapshot(project_name=key),
                    )
                snapshot = graph_to_snapshot(key, config.knowledge_graph)
                return KnowledgeGraphOutput(
                    success=True,
                    message=f"Project '{key}' loaded.",
                    payload=snapshot,
                )

            case "DELETE":
                key = input_.key
                if not key:
                    return KnowledgeGraphOutput(
                        success=False,
                        message="DELETE requires a key (project name).",
                    )
                removed = project_store.delete(key)
                if removed:
                    return KnowledgeGraphOutput(
                        success=True,
                        message=f"Project '{key}' deleted.",
                    )
                return KnowledgeGraphOutput(
                    success=False,
                    message=f"Project '{key}' not found.",
                )

            case _:
                return KnowledgeGraphOutput(
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
        input_model=KnowledgeGraphInput,
        output_model=KnowledgeGraphOutput,
        handler=handler,
    )
