"""
Base models for nodes and edges in the knowledge graph.
"""
from __future__ import annotations

import uuid
from typing import Literal
from pydantic import BaseModel, Field


NodeType = Literal[
    "project",
    "feature",
    "goal",
    "guiding_principle",
    "requirement",
    "capability",
    "use_case",
    "scenario",
    "design_artifact",
    "decision",
    "constraint",
    "component",
    "dependency",
    "documentation_artifact",
]



EdgeType = Literal[
    "HAS_GOAL",
    "HAS_REQUIREMENT",
    "HAS_CAPABILITY",
    "HAS_COMPONENT",
    "HAS_DEPENDENCY",
    "HAS_CONSTRAINT",
    "HAS_RULE",
    "HAS_QUIZ",
    "HAS_QUERY_PATTERN",
    "SATISFIED_BY",
    "REALIZED_BY",
    "DEPENDS_ON",
    "CONSTRAINS",
    "DESCRIBED_BY",
    "DOCUMENTED_BY",
    "SUPPORTS",
    "INFORMS",
    "HAS_SCENARIO",
    "INSTANCE_OF",
]


class BaseNode(BaseModel):
    """
    Base class for all knowledge graph nodes.
    
    All nodes have an ID and a name. Subclasses add domain-specific fields.
    IDs are immutable; content fields can be updated.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique identifier for this node")
    name: str = Field(default_factory=lambda: "missing_name",  description="Human-readable name")
    
    model_config = {"frozen": False}


class BaseEdge(BaseModel):
    """
    Base class for all knowledge graph edges.
    
    Edges represent typed relationships between nodes.
    """
    edge_type: EdgeType = Field(..., description="Type of relationship")
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    
    model_config = {"frozen": True}
