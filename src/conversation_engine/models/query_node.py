"""
Graph query pattern models for AI reasoning.

These models define reusable query patterns that the AI can use to analyze
the knowledge graph for gaps, inconsistencies, and completeness.
"""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from conversation_engine.models.base import EdgeType, NodeType, BaseNode

QueryIntent = Literal[
    "gap_detection",
    "orphan_detection",
    "coverage_detection",
    "completeness_check",
    "design_completeness",
    "behavior_coverage",
    "impact_analysis",
    "lineage_trace",
]

OutputKind = Literal[
    "finding_set",
    "impact_report",
    "trace_report",
]


class EdgeCheck(BaseModel):
    """
    Defines a check for the presence/absence of edges from a node.
    """
    edge_type: EdgeType = Field(..., description="Type of edge to check")
    target_node_types: List[NodeType] = Field(
        ...,
        description="Expected target node types"
    )
    expected_min_count: int = Field(
        ...,
        description="Minimum expected count of edges"
    )


class TraversalSpec(BaseModel):
    """
    Defines a graph traversal for impact analysis.
    """
    start_edges: List[EdgeType] = Field(
        ...,
        description="Edge types to start traversal from"
    )
    max_depth: int = Field(..., description="Maximum traversal depth")
    include_node_types: List[NodeType] = Field(
        ...,
        description="Node types to include in the result"
    )


class PathStep(BaseModel):
    """
    Defines a single step in a path pattern for lineage tracing.
    """
    edge_type: EdgeType = Field(..., description="Edge type for this step")
    target_node_types: List[NodeType] = Field(
        ...,
        description="Valid target node types for this step"
    )


class GraphQueryPattern(BaseNode):
    """
    A reusable query pattern for analyzing the knowledge graph.

    Query patterns are AI reasoning tools that detect gaps, orphans,
    and completeness issues in the graph structure.
    """
    node_type: NodeType = Field(NodeType.QUERY_PATTERN, description="Type of this node")
    description: str = Field(..., description="What this query detects")

    subject_node_type: NodeType = Field(
        ...,
        description="The node type this query operates on"
    )
    query_intent: QueryIntent = Field(
        ...,
        description="The purpose of this query"
    )

    checks: Optional[List[EdgeCheck]] = Field(
        None,
        description="Edge checks to perform (for gap/orphan detection)"
    )
    traversal: Optional[TraversalSpec] = Field(
        None,
        description="Traversal specification (for impact analysis)"
    )
    path_pattern: Optional[List[PathStep]] = Field(
        None,
        description="Path pattern to follow (for lineage tracing)"
    )

    output_kind: OutputKind = Field(..., description="Type of output to produce")

    model_config = {"frozen": True}
