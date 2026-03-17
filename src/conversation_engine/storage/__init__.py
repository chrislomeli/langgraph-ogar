"""
Graph storage layer for the Conversation Engine.

Provides in-memory graph storage with proper graph semantics:
- Nodes and edges as first-class entities
- Queryable edge relationships
- Graph traversal operations
- Index-backed lookups
"""
from conversation_engine.storage.graph import KnowledgeGraph
from conversation_engine.storage.queries import GraphQueries

__all__ = [
    "KnowledgeGraph",
    "GraphQueries",
]
