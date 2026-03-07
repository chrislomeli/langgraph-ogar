"""
Persistence tools — save, load, and list compositions in Memgraph.

These wrap the symbolic_music persistence layer
as LangGraph-compatible tools for agent consumption.

Implemented at Milestone 7 of the LangGraph tutorial.
"""

from __future__ import annotations

# TODO (M7): Implement these tools:
#
# - save_composition_tool: CompositionSpec → Memgraph (content-addressed)
#   Wraps symbolic_music.persistence.writer
#
# - load_composition_tool: composition_id → CompositionSpec
#   Wraps symbolic_music.persistence.reader
#
# - list_compositions_tool: → list of saved compositions
#   Wraps symbolic_music.persistence.reader
