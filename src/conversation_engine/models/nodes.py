"""
Node type models for the knowledge graph.

Each node type represents a specific kind of architectural knowledge.
"""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import Field

from conversation_engine.models.base import BaseNode


class Feature(BaseNode):
    """
    A feature represents a high-level system capability or product offering.
    """
    description: str = Field(..., description="Detailed description of the feature")


class Goal(BaseNode):
    """
    A goal represents a desired outcome or objective.
    """
    statement: str = Field(..., description="Goal statement describing the desired outcome")


class GuidingPrinciple(BaseNode):
    """
    A guiding principle represents a design or architectural principle.
    """
    statement: str = Field(..., description="The principle statement")


RequirementType = Literal["functional", "non_functional", "constraint"]


class Requirement(BaseNode):
    """
    A requirement represents a specific system need or constraint.
    """
    requirement_type: Optional[RequirementType] = Field(
        None, 
        description="Type of requirement"
    )
    description: Optional[str] = Field(
        None,
        description="Detailed description of the requirement"
    )


class Capability(BaseNode):
    """
    A capability represents an observable system behavior.
    """
    description: Optional[str] = Field(
        None,
        description="Description of what the capability enables"
    )


class UseCase(BaseNode):
    """
    A use case represents a specific user interaction or workflow.
    """
    description: Optional[str] = Field(
        None,
        description="Description of the use case"
    )


class Scenario(BaseNode):
    """
    A scenario represents a concrete instance or example of a use case.
    """
    description: Optional[str] = Field(
        None,
        description="Description of the scenario"
    )


class DesignArtifact(BaseNode):
    """
    A design artifact represents a design decision or architectural element.
    """
    statement: str = Field(..., description="Statement describing the design artifact")


class Decision(BaseNode):
    """
    A decision represents an architectural or design decision.
    """
    statement: str = Field(..., description="The decision that was made")
    rationale: Optional[str] = Field(None, description="Why this decision was made")


class Constraint(BaseNode):
    """
    A constraint represents a limitation or restriction on the system.
    """
    statement: str = Field(..., description="The constraint statement")


class Component(BaseNode):
    """
    A component represents a system module or architectural component.
    """
    description: Optional[str] = Field(
        None,
        description="Description of the component's purpose"
    )
    has_no_dependencies: bool = Field(
        False,
        description="Explicitly marks that this component has no dependencies"
    )


class Dependency(BaseNode):
    """
    A dependency represents an external system, library, or service.
    """
    description: Optional[str] = Field(
        None,
        description="Description of the dependency"
    )


class DocumentationArtifact(BaseNode):
    """
    A documentation artifact represents documentation or explanatory content.
    """
    description: Optional[str] = Field(
        None,
        description="Description of the documentation"
    )
