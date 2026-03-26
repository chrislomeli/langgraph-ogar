"""
ProjectSnapshot — flat, business-level view of a knowledge graph.

This is the payload the LLM produces and consumes.  It uses human-readable
names instead of IDs and inline references instead of edges.  A facade
converts between ``ProjectSnapshot`` and ``KnowledgeGraph``.

The LLM never sees nodes, edges, or IDs.

Design principles:
- Every spec model uses **name-based references** (e.g. ``goal_ref``)
- The facade resolves names → IDs and wires the correct edge types/directions
- Adding a new concept = add a spec here + add conversion in the facade
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ── Individual spec models ─────────────────────────────────────────

class GoalSpec(BaseModel):
    """A desired outcome or objective."""
    name: str = Field(..., description="Human-readable goal name")
    statement: str = Field(..., description="Goal statement describing the desired outcome")


class RequirementSpec(BaseModel):
    """A specific system need linked to a goal."""
    name: str = Field(..., description="Human-readable requirement name")
    goal_ref: str = Field(..., description="Name of the goal this requirement satisfies")
    requirement_type: Optional[Literal["functional", "non_functional", "constraint"]] = Field(
        None, description="Type of requirement"
    )
    description: Optional[str] = Field(None, description="Detailed description")


class CapabilitySpec(BaseModel):
    """An observable system behaviour linked to requirements."""
    name: str = Field(..., description="Human-readable capability name")
    requirement_refs: List[str] = Field(
        default_factory=list,
        description="Names of requirements this capability realises",
    )
    description: Optional[str] = Field(None, description="Description of what the capability enables")


class ComponentSpec(BaseModel):
    """A system module linked to capabilities and dependencies."""
    name: str = Field(..., description="Human-readable component name")
    capability_refs: List[str] = Field(
        default_factory=list,
        description="Names of capabilities this component realises",
    )
    dependency_refs: List[str] = Field(
        default_factory=list,
        description="Names of dependencies this component depends on",
    )
    has_no_dependencies: bool = Field(
        False,
        description="Explicitly marks that this component has no dependencies",
    )
    description: Optional[str] = Field(None, description="Description of the component's purpose")


class ConstraintSpec(BaseModel):
    """A limitation or restriction on the system."""
    name: str = Field(..., description="Human-readable constraint name")
    statement: str = Field(..., description="The constraint statement")


class DependencySpec(BaseModel):
    """An external system, library, or service."""
    name: str = Field(..., description="Human-readable dependency name")
    description: Optional[str] = Field(None, description="Description of the dependency")


# ── Top-level snapshot ─────────────────────────────────────────────

) class ProjectSnapshot(BaseModel):

    """
    Flat, business-level representation of a project's knowledge graph.

    This is the only structure the LLM interacts with.  It contains no
    node IDs, no edge types, and no graph-level concepts.  A facade
    converts it to/from the internal ``KnowledgeGraph``.
    """
    project_name: str = Field(..., description="Unique project identifier")
    goals: List[GoalSpec] = Field(default_factory=list, description="Project goals")
    requirements: List[RequirementSpec] = Field(default_factory=list, description="Requirements linked to goals")
    capabilities: List[CapabilitySpec] = Field(default_factory=list, description="Capabilities linked to requirements")
    components: List[ComponentSpec] = Field(default_factory=list, description="Components linked to capabilities")
    constraints: List[ConstraintSpec] = Field(default_factory=list, description="System constraints")
    dependencies: List[DependencySpec] = Field(default_factory=list, description="External dependencies")

    model_config = {"frozen": False}
