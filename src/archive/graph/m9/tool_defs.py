"""
Tool definitions — M9: ToolSpec contracts for every domain operation.

KEY CONCEPT: Each domain operation becomes a ToolSpec — a frozen contract
with Pydantic input/output models and a handler function. The handler
wraps the existing domain logic (DeterministicPlanner, PatternCompiler, etc.)
without changing it.

The Pydantic models serve double duty:
  1. Input/output validation (enforced by LocalToolClient)
  2. JSON Schema export (for MCP compatibility and LLM tool descriptions)

Tools defined here:
  - parse_sketch: user message → Sketch
  - plan_composition: Sketch → PlanBundle
  - compile_composition: PlanBundle → CompileResult
  - refine_plan: PlanBundle + prompt → refined PlanBundle
  - save_project: artifacts → ProjectRecord
  - load_project: title → ProjectRecord
  - list_projects: → list of project summaries
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from framework.langgraph_ext.tool_client.spec import ToolSpec
from framework.langgraph_ext.tool_client.registry import ToolRegistry

from intent.sketch_models import Sketch
from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler
from intent.compiler_interface import CompileOptions


# ── Shared instances (same as M8 subgraph nodes) ──────────────────

_planner = DeterministicPlanner()
_compiler = PatternCompiler()


# ══════════════════════════════════════════════════════════════════
# Pydantic input/output models for each tool
# ══════════════════════════════════════════════════════════════════


# ── parse_sketch ──────────────────────────────────────────────────

class ParseSketchInput(BaseModel):
    """Input for parse_sketch tool."""
    user_message: str = Field(..., description="The user's free-text prompt")


class ParseSketchOutput(BaseModel):
    """Output from parse_sketch tool."""
    sketch: Any = Field(..., description="The parsed Sketch object")

    model_config = {"arbitrary_types_allowed": True}


# ── plan_composition ─────────────────────────────────────────────

class PlanCompositionInput(BaseModel):
    """Input for plan_composition tool."""
    sketch: Any = Field(..., description="A Sketch object to plan from")

    model_config = {"arbitrary_types_allowed": True}


class PlanCompositionOutput(BaseModel):
    """Output from plan_composition tool."""
    plan: Any = Field(..., description="The generated PlanBundle")

    model_config = {"arbitrary_types_allowed": True}


# ── compile_composition ──────────────────────────────────────────

class CompileCompositionInput(BaseModel):
    """Input for compile_composition tool."""
    plan: Any = Field(..., description="A PlanBundle to compile")
    regenerate_voices: Optional[set] = Field(
        default=None, description="Voice IDs to regenerate (None = all)"
    )
    previous_compile_result: Any = Field(
        default=None, description="Previous CompileResult for scoped recompilation"
    )

    model_config = {"arbitrary_types_allowed": True}


class CompileCompositionOutput(BaseModel):
    """Output from compile_composition tool."""
    compile_result: Any = Field(..., description="The CompileResult")

    model_config = {"arbitrary_types_allowed": True}


# ── refine_plan ──────────────────────────────────────────────────

class RefinePlanInput(BaseModel):
    """Input for refine_plan tool."""
    plan: Any = Field(..., description="The current PlanBundle to refine")
    prompt: str = Field(..., description="What the user wants to change")

    model_config = {"arbitrary_types_allowed": True}


class RefinePlanOutput(BaseModel):
    """Output from refine_plan tool."""
    plan: Any = Field(..., description="The refined PlanBundle")

    model_config = {"arbitrary_types_allowed": True}


# ── save_project ─────────────────────────────────────────────────

class SaveProjectInput(BaseModel):
    """Input for save_project tool."""
    title: str = Field(..., description="Project title")
    sketch: Any = Field(default=None, description="Sketch object")
    plan: Any = Field(default=None, description="PlanBundle object")
    compile_result: Any = Field(default=None, description="CompileResult object")

    model_config = {"arbitrary_types_allowed": True}


class SaveProjectOutput(BaseModel):
    """Output from save_project tool."""
    title: str
    version: int
    saved_at: str

    model_config = {"arbitrary_types_allowed": True}


# ── load_project ─────────────────────────────────────────────────

class LoadProjectInput(BaseModel):
    """Input for load_project tool."""
    title: str = Field(..., description="Project title to load")
    version: Optional[int] = Field(default=None, description="Specific version (None = latest)")


class LoadProjectOutput(BaseModel):
    """Output from load_project tool."""
    title: str
    version: int
    saved_at: str
    sketch: Any = None
    plan: Any = None
    compile_result: Any = None

    model_config = {"arbitrary_types_allowed": True}


# ── list_projects ────────────────────────────────────────────────

class ListProjectsInput(BaseModel):
    """Input for list_projects tool — no arguments needed."""
    pass


class ListProjectsOutput(BaseModel):
    """Output from list_projects tool."""
    projects: list[dict] = Field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# Handler functions — thin wrappers around domain logic
# ══════════════════════════════════════════════════════════════════


def _handle_parse_sketch(input: ParseSketchInput) -> ParseSketchOutput:
    sketch = Sketch(prompt=input.user_message)
    return ParseSketchOutput(sketch=sketch)


def _handle_plan_composition(input: PlanCompositionInput) -> PlanCompositionOutput:
    plan = _planner.plan(input.sketch)
    return PlanCompositionOutput(plan=plan)


def _handle_compile_composition(input: CompileCompositionInput) -> CompileCompositionOutput:
    if input.regenerate_voices and input.previous_compile_result:
        options = CompileOptions(regenerate_voices=input.regenerate_voices)
        result = _compiler.compile(input.plan, options=options, previous=input.previous_compile_result)
    else:
        result = _compiler.compile(input.plan)
    return CompileCompositionOutput(compile_result=result)


def _handle_refine_plan(input: RefinePlanInput) -> RefinePlanOutput:
    refined = _planner.refine(input.plan, input.prompt)
    return RefinePlanOutput(plan=refined)


# ══════════════════════════════════════════════════════════════════
# Persistence handlers — need a store instance, so they're factories
# ══════════════════════════════════════════════════════════════════


def _make_save_handler(store):
    """Factory: create a save_project handler with the store baked in."""
    def handler(input: SaveProjectInput) -> SaveProjectOutput:
        record = store.save(
            title=input.title,
            sketch=input.sketch,
            plan=input.plan,
            compile_result=input.compile_result,
        )
        return SaveProjectOutput(
            title=record.title,
            version=record.version,
            saved_at=record.saved_at,
        )
    return handler


def _make_load_handler(store):
    """Factory: create a load_project handler with the store baked in."""
    def handler(input: LoadProjectInput) -> LoadProjectOutput:
        record = store.load(input.title, version=input.version)
        return LoadProjectOutput(
            title=record.title,
            version=record.version,
            saved_at=record.saved_at,
            sketch=record.sketch,
            plan=record.plan,
            compile_result=record.compile_result,
        )
    return handler


def _make_list_handler(store):
    """Factory: create a list_projects handler with the store baked in."""
    def handler(input: ListProjectsInput) -> ListProjectsOutput:
        projects = store.list_projects()
        return ListProjectsOutput(projects=projects)
    return handler


# ══════════════════════════════════════════════════════════════════
# Registry builder — creates a ToolRegistry with all tools registered
# ══════════════════════════════════════════════════════════════════


def build_tool_registry(store=None) -> ToolRegistry:
    """Build a ToolRegistry with all domain tools registered.

    Args:
        store: MusicStore instance for persistence tools.
               If None, persistence tools are not registered.

    Returns:
        A ToolRegistry with all available tools.
    """
    registry = ToolRegistry()

    # Intent pipeline tools
    registry.register(ToolSpec(
        name="parse_sketch",
        description="Parse a user's free-text prompt into a Sketch object",
        input_model=ParseSketchInput,
        output_model=ParseSketchOutput,
        handler=_handle_parse_sketch,
    ))

    registry.register(ToolSpec(
        name="plan_composition",
        description="Generate a PlanBundle from a Sketch using DeterministicPlanner",
        input_model=PlanCompositionInput,
        output_model=PlanCompositionOutput,
        handler=_handle_plan_composition,
    ))

    registry.register(ToolSpec(
        name="compile_composition",
        description="Compile a PlanBundle into a CompileResult using PatternCompiler",
        input_model=CompileCompositionInput,
        output_model=CompileCompositionOutput,
        handler=_handle_compile_composition,
    ))

    registry.register(ToolSpec(
        name="refine_plan",
        description="Apply a refinement to an existing PlanBundle",
        input_model=RefinePlanInput,
        output_model=RefinePlanOutput,
        handler=_handle_refine_plan,
    ))

    # Persistence tools (only if store provided)
    if store is not None:
        registry.register(ToolSpec(
            name="save_project",
            description="Save a project's artifacts to persistent storage",
            input_model=SaveProjectInput,
            output_model=SaveProjectOutput,
            handler=_make_save_handler(store),
        ))

        registry.register(ToolSpec(
            name="load_project",
            description="Load a project's artifacts from persistent storage",
            input_model=LoadProjectInput,
            output_model=LoadProjectOutput,
            handler=_make_load_handler(store),
        ))

        registry.register(ToolSpec(
            name="list_projects",
            description="List all saved projects",
            input_model=ListProjectsInput,
            output_model=ListProjectsOutput,
            handler=_make_list_handler(store),
        ))

    return registry
