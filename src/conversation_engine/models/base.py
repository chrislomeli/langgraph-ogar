"""
Base models for nodes and edges in the knowledge graph.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


NodeType = Literal[
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
    id: str = Field(..., description="Unique identifier for this node")
    name: str = Field(..., description="Human-readable name")
    
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
