"""
Tool definitions — same as M9, copied for self-contained milestone.

See M9 tool_defs.py for detailed documentation.
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


_planner = DeterministicPlanner()
_compiler = PatternCompiler()


# ── Pydantic I/O models ─────────────────────────────────────────

class ParseSketchInput(BaseModel):
    user_message: str = Field(..., description="The user's free-text prompt")

class ParseSketchOutput(BaseModel):
    sketch: Any = Field(..., description="The parsed Sketch object")
    model_config = {"arbitrary_types_allowed": True}


class PlanCompositionInput(BaseModel):
    sketch: Any = Field(..., description="A Sketch object to plan from")
    model_config = {"arbitrary_types_allowed": True}

class PlanCompositionOutput(BaseModel):
    plan: Any = Field(..., description="The generated PlanBundle")
    model_config = {"arbitrary_types_allowed": True}


class CompileCompositionInput(BaseModel):
    plan: Any = Field(..., description="A PlanBundle to compile")
    regenerate_voices: Optional[set] = Field(default=None)
    previous_compile_result: Any = Field(default=None)
    model_config = {"arbitrary_types_allowed": True}

class CompileCompositionOutput(BaseModel):
    compile_result: Any = Field(..., description="The CompileResult")
    model_config = {"arbitrary_types_allowed": True}


class RefinePlanInput(BaseModel):
    plan: Any = Field(..., description="The current PlanBundle to refine")
    prompt: str = Field(..., description="What the user wants to change")
    model_config = {"arbitrary_types_allowed": True}

class RefinePlanOutput(BaseModel):
    plan: Any = Field(..., description="The refined PlanBundle")
    model_config = {"arbitrary_types_allowed": True}


class SaveProjectInput(BaseModel):
    title: str = Field(..., description="Project title")
    sketch: Any = Field(default=None)
    plan: Any = Field(default=None)
    compile_result: Any = Field(default=None)
    model_config = {"arbitrary_types_allowed": True}

class SaveProjectOutput(BaseModel):
    title: str
    version: int
    saved_at: str
    model_config = {"arbitrary_types_allowed": True}


class LoadProjectInput(BaseModel):
    title: str = Field(..., description="Project title to load")
    version: Optional[int] = Field(default=None)

class LoadProjectOutput(BaseModel):
    title: str
    version: int
    saved_at: str
    sketch: Any = None
    plan: Any = None
    compile_result: Any = None
    model_config = {"arbitrary_types_allowed": True}


class ListProjectsInput(BaseModel):
    pass

class ListProjectsOutput(BaseModel):
    projects: list[dict] = Field(default_factory=list)


# ── Handlers ─────────────────────────────────────────────────────

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


def _make_save_handler(store):
    def handler(input: SaveProjectInput) -> SaveProjectOutput:
        record = store.save(title=input.title, sketch=input.sketch, plan=input.plan, compile_result=input.compile_result)
        return SaveProjectOutput(title=record.title, version=record.version, saved_at=record.saved_at)
    return handler

def _make_load_handler(store):
    def handler(input: LoadProjectInput) -> LoadProjectOutput:
        record = store.load(input.title, version=input.version)
        return LoadProjectOutput(title=record.title, version=record.version, saved_at=record.saved_at, sketch=record.sketch, plan=record.plan, compile_result=record.compile_result)
    return handler

def _make_list_handler(store):
    def handler(input: ListProjectsInput) -> ListProjectsOutput:
        return ListProjectsOutput(projects=store.list_projects())
    return handler


# ── Registry builder ─────────────────────────────────────────────

def build_tool_registry(store=None) -> ToolRegistry:
    registry = ToolRegistry()

    registry.register(ToolSpec(name="parse_sketch", description="Parse user prompt into Sketch", input_model=ParseSketchInput, output_model=ParseSketchOutput, handler=_handle_parse_sketch))
    registry.register(ToolSpec(name="plan_composition", description="Generate PlanBundle from Sketch", input_model=PlanCompositionInput, output_model=PlanCompositionOutput, handler=_handle_plan_composition))
    registry.register(ToolSpec(name="compile_composition", description="Compile PlanBundle into CompileResult", input_model=CompileCompositionInput, output_model=CompileCompositionOutput, handler=_handle_compile_composition))
    registry.register(ToolSpec(name="refine_plan", description="Apply refinement to PlanBundle", input_model=RefinePlanInput, output_model=RefinePlanOutput, handler=_handle_refine_plan))

    if store is not None:
        registry.register(ToolSpec(name="save_project", description="Save project to store", input_model=SaveProjectInput, output_model=SaveProjectOutput, handler=_make_save_handler(store)))
        registry.register(ToolSpec(name="load_project", description="Load project from store", input_model=LoadProjectInput, output_model=LoadProjectOutput, handler=_make_load_handler(store)))
        registry.register(ToolSpec(name="list_projects", description="List all saved projects", input_model=ListProjectsInput, output_model=ListProjectsOutput, handler=_make_list_handler(store)))

    return registry
