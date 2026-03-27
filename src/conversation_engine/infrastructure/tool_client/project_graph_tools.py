"""
Knowledge-graph tool — business-level CRUD operations for the ReAct agent.

The LLM interacts with ``ProjectSnapshot`` (flat, name-based references).
It never sees nodes, edges, or IDs.  The tool handler delegates all
operations to a ``ProjectService``.

Methods:
    CREATE(payload)  — persist a new project from a ProjectSnapshot
    READ(key)        — retrieve an existing project as a ProjectSnapshot
    UPDATE(key, payload) — replace an existing project
    DELETE(key)      — remove a project by name
    VALIDATE(key)    — run integrity checks and return findings
"""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from conversation_engine.infrastructure.tool_client.spec import ToolSpec
from conversation_engine.storage.snapshot import ProjectSnapshot


# ── I/O models ─────────────────────────────────────────────────────
class CRUDMethod(str, Enum):
    CREATE   = "CREATE"
    READ     = "READ"
    UPDATE   = "UPDATE"
    DELETE   = "DELETE"
    VALIDATE = "VALIDATE"


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
        description="The project data — returned by READ and CREATE, None for DELETE.",
    )
    findings: Optional[List[str]] = Field(
        None,
        description="Validation findings — returned by VALIDATE and CREATE/UPDATE.",
    )


# ── Service-backed tool factory ─────────────────────────────────────

def make_project_service_tool(service) -> ToolSpec:
    """
    Create a knowledge_graph ToolSpec backed by a ProjectService.

    This is the primary factory.  The service owns all domain logic
    (validation, conversion, persistence).  The tool is a thin wrapper.

    Parameters
    ----------
    service : ProjectService
        The single gateway for all project operations.
    """

    def handler(input_: ProjectGraphInput) -> ProjectGraphOutput:
        match input_.method:
            case CRUDMethod.CREATE | CRUDMethod.UPDATE:
                if input_.payload is None:
                    return ProjectGraphOutput(
                        success=False,
                        message=f"{input_.method.value} requires a payload (ProjectSnapshot).",
                    )
                result = service.save(input_.payload)
                finding_msgs = [f.message for f in result.findings] if result.findings else None
                return ProjectGraphOutput(
                    success=result.success,
                    message=result.message,
                    payload=result.snapshot,
                    findings=finding_msgs,
                )

            case CRUDMethod.READ:
                if not input_.key:
                    return ProjectGraphOutput(
                        success=False,
                        message="READ requires a key (project name).",
                    )
                result = service.get(input_.key)
                return ProjectGraphOutput(
                    success=result.success,
                    message=result.message,
                    payload=result.snapshot,
                )

            case CRUDMethod.DELETE:
                if not input_.key:
                    return ProjectGraphOutput(
                        success=False,
                        message="DELETE requires a key (project name).",
                    )
                result = service.delete(input_.key)
                return ProjectGraphOutput(
                    success=result.success,
                    message=result.message,
                )

            case CRUDMethod.VALIDATE:
                if not input_.key:
                    return ProjectGraphOutput(
                        success=False,
                        message="VALIDATE requires a key (project name).",
                    )
                result = service.validate(input_.key)
                finding_msgs = [f.message for f in result.findings] if result.findings else None
                return ProjectGraphOutput(
                    success=result.success,
                    message=result.message,
                    findings=finding_msgs,
                )

            case _:
                return ProjectGraphOutput(
                    success=False,
                    message=f"Unknown method '{input_.method}'. "
                            "Use CREATE, READ, UPDATE, DELETE, or VALIDATE.",
                )

    return ToolSpec(
        name="knowledge_graph",
        description=(
            "Perform business-level operations on a project's knowledge graph. "
            "This is the sole interface for persisting and retrieving project data.\n\n"
            "Methods:\n"
            "  CREATE(payload)  — persist a new project from a ProjectSnapshot\n"
            "  READ(key)        — retrieve an existing project as a ProjectSnapshot\n"
            "  UPDATE(payload)  — replace an existing project (upsert)\n"
            "  DELETE(key)      — remove a project by name\n"
            "  VALIDATE(key)    — run integrity checks and return findings\n\n"
            "The payload is a ProjectSnapshot with goals, requirements, capabilities, "
            "components, constraints, and dependencies. Use name-based references "
            "(e.g. a requirement's goal_ref is the goal's name, not an ID)."
        ),
        input_model=ProjectGraphInput,
        output_model=ProjectGraphOutput,
        handler=handler,
    )


# ── Legacy tool factory (backwards compatibility) ────────────────────

def make_project_graph_tool(project_store) -> ToolSpec:
    """
    LEGACY: Create a knowledge_graph ToolSpec bound to a ProjectStore.

    Prefer ``make_project_service_tool(service)`` for new code.
    This factory builds an ArchitecturalProjectService internally.
    """
    from conversation_engine.services.architectural_project_service import (
        ArchitecturalProjectService,
    )
    service = ArchitecturalProjectService(store=project_store)
    return make_project_service_tool(service)
