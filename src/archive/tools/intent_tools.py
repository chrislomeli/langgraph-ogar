"""
Intent pipeline tools — Sketch → Plan → Compile.

These wrap the intent layer (DeterministicPlanner, PatternCompiler)
as LangGraph-compatible tools for agent consumption.

Implemented at Milestone 6 of the LangGraph tutorial.
"""

from __future__ import annotations

# TODO (M6): Implement these tools:
#
# - parse_sketch_tool: Free-text prompt → Sketch model
# - plan_composition_tool: Sketch → PlanBundle (via DeterministicPlanner)
# - compile_voice_tool: PlanBundle + voice_name → CompileResult (via PatternCompiler)
# - refine_plan_tool: PlanBundle + RefinementRequest → PlanBundle (M8)
#
# Each tool will follow the same pattern as project_tools.py:
#   1. Define a @tool function with Annotated parameters
#   2. Delegate to the domain logic in src/intent/
#   3. Return JSON-serialized Pydantic output
