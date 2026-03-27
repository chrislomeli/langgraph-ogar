"""
Graph storage layer for the Conversation Engine.

Provides in-memory graph storage with proper graph semantics:
- Nodes and edges as first-class entities
- Queryable edge relationships
- Graph traversal operations
- Index-backed lookups
- Project-level CRUD for domain configurations
"""
from conversation_engine.storage.graph import KnowledgeGraph
from conversation_engine.storage.queries import GraphQueries
from conversation_engine.storage.project_store import (
    ProjectStore,
    InMemoryProjectStore,
)
from conversation_engine.storage.file_project_store import FileProjectStore
from conversation_engine.storage.project_specification import (
    ProjectSpecification,
    GoalSpec,
    RequirementSpec,
    CapabilitySpec,
    ComponentSpec,
    ConstraintSpec,
    DependencySpec,
)
from conversation_engine.storage.project_graph_facade import (
    snapshot_to_graph,
    graph_to_snapshot,
    SnapshotConversionError,
)

__all__ = [
    "KnowledgeGraph",
    "GraphQueries",
    "ProjectStore",
    "InMemoryProjectStore",
    "FileProjectStore",
    # Snapshot
    "ProjectSpecification",
    "GoalSpec",
    "RequirementSpec",
    "CapabilitySpec",
    "ComponentSpec",
    "ConstraintSpec",
    "DependencySpec",
    "snapshot_to_graph",
    "graph_to_snapshot",
    "SnapshotConversionError",
]
