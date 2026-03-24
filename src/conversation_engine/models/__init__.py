"""
Domain models for the Reusable Conversation Engine.
"""
from conversation_engine.models.base import NodeType, EdgeType, BaseNode, BaseEdge
from conversation_engine.models.nodes import (
    Feature,
    Goal,
    GuidingPrinciple,
    Requirement,
    Capability,
    UseCase,
    Scenario,
    DesignArtifact,
    Decision,
    Constraint,
    Component,
    Dependency,
    DocumentationArtifact,
)
from conversation_engine.models.traceability import (
    GoalRequirementTrace,
    RequirementCapabilityTrace,
    CapabilityComponentTrace,
    ComponentDependencyTrace,
)
from conversation_engine.models.rules import (
    RuleType,
    Severity,
    IntegrityRule,
)
from conversation_engine.models.queries import (
    QueryIntent,
    OutputKind,
    EdgeCheck,
    TraversalSpec,
    PathStep,
    GraphQueryPattern,
)
from conversation_engine.models.assessment import (
    AssessmentType,
    Assessment,
)

# DomainConfig is intentionally NOT imported here to avoid a circular
# import (domain_config → storage.graph → models.base → models/__init__).
# Import it directly:  from conversation_engine.models.domain_config import DomainConfig

__all__ = [
    "NodeType",
    "EdgeType",
    "BaseNode",
    "BaseEdge",
    "Feature",
    "Goal",
    "GuidingPrinciple",
    "Requirement",
    "Capability",
    "UseCase",
    "Scenario",
    "DesignArtifact",
    "Decision",
    "Constraint",
    "Component",
    "Dependency",
    "DocumentationArtifact",
    "GoalRequirementTrace",
    "RequirementCapabilityTrace",
    "CapabilityComponentTrace",
    "ComponentDependencyTrace",
    "RuleType",
    "Severity",
    "IntegrityRule",
    "QueryIntent",
    "OutputKind",
    "EdgeCheck",
    "TraversalSpec",
    "PathStep",
    "GraphQueryPattern",
    "AssessmentType",
    "Assessment",
]
