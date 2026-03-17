"""
Traceability models for mapping relationships between layers.

These models capture the explicit traceability chains:
  Goal → Requirement → Capability → Component → Dependency
"""
from __future__ import annotations

from typing import List
from pydantic import BaseModel, Field


class GoalRequirementTrace(BaseModel):
    """
    Maps a goal to the requirements that satisfy it.
    """
    goal_id: str = Field(..., description="Goal identifier")
    requirement_ids: List[str] = Field(
        default_factory=list,
        description="List of requirement IDs that satisfy this goal"
    )


class RequirementCapabilityTrace(BaseModel):
    """
    Maps a requirement to the capabilities that realize it.
    """
    requirement_id: str = Field(..., description="Requirement identifier")
    capability_ids: List[str] = Field(
        default_factory=list,
        description="List of capability IDs that realize this requirement"
    )


class CapabilityComponentTrace(BaseModel):
    """
    Maps a capability to the components that implement it.
    """
    capability_id: str = Field(..., description="Capability identifier")
    component_ids: List[str] = Field(
        default_factory=list,
        description="List of component IDs that implement this capability"
    )


class ComponentDependencyTrace(BaseModel):
    """
    Maps a component to its dependencies.
    """
    component_id: str = Field(..., description="Component identifier")
    dependency_ids: List[str] = Field(
        default_factory=list,
        description="List of dependency IDs (external systems, libraries, etc.)"
    )
