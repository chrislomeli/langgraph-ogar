"""
Music domain tools — rendering and domain operations.

These wrap the symbolic_music layer (render_composition, persistence)
as LangGraph-compatible tools for agent consumption.

Implemented at Milestone 6 of the LangGraph tutorial.
"""

from __future__ import annotations

# TODO (M6): Implement these tools:
#
# - render_composition_tool: CompositionSpec → music21 Score → file path
#   Wraps symbolic_music.rendering.music21.render_composition()
#
# - validate_composition_tool: CompositionSpec → validation report
#   Checks domain invariants before rendering
