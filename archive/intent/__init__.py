"""
Intent layer: Sketch → Plan → Compilation pipeline.

Modules:
- sketch_models: User-facing input (Sketch, VoiceHint, SeedRef, InlineSeed)
- plan_models: AI-facing output (PlanBundle, sub-plans, refinement protocol)
- engine: DeterministicPlanner (Sketch → PlanBundle)
- compiler_interface: ABCs (PlanCompiler, IREditor) and result types
- compiler: PatternCompiler (PlanBundle → CompileResult)
"""

from intent.sketch_models import (
    InlineNoteSpec,
    InlineSeed,
    Sketch,
    SeedKind,
    SeedRef,
    VoiceHint,
)

from intent.plan_models import (
    ChordEvent,
    ChordQuality,
    DensityLevel,
    EnergyLevel,
    FormPlan,
    GrooveFeel,
    GroovePlan,
    GrooveSectionPlan,
    HarmonyPlan,
    HarmonySectionPlan,
    IRRefinementRequest,
    PlanBundle,
    RefinementRequest,
    RefinementScope,
    RegisterBand,
    RenderPlan,
    RenderTarget,
    SectionPlan,
    SectionRole,
    TimelinePlacement,
    VoicePlan,
    VoiceRole,
    VoiceSpec,
)

from intent.compiler_interface import (
    CompileOptions,
    CompileResult,
    IREditor,
    PlanCompiler,
)

from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler

__all__ = [
    # Sketch
    "Sketch",
    "VoiceHint",
    "SeedRef",
    "SeedKind",
    "InlineSeed",
    "InlineNoteSpec",
    # Plan
    "PlanBundle",
    "VoicePlan",
    "VoiceSpec",
    "VoiceRole",
    "FormPlan",
    "SectionPlan",
    "SectionRole",
    "TimelinePlacement",
    "HarmonyPlan",
    "HarmonySectionPlan",
    "ChordEvent",
    "ChordQuality",
    "GroovePlan",
    "GrooveSectionPlan",
    "GrooveFeel",
    "RenderPlan",
    "RenderTarget",
    "EnergyLevel",
    "DensityLevel",
    "RegisterBand",
    "RefinementRequest",
    "RefinementScope",
    "IRRefinementRequest",
    # Compiler interface
    "CompileOptions",
    "CompileResult",
    "PlanCompiler",
    "IREditor",
    # Implementations
    "DeterministicPlanner",
    "PatternCompiler",
]
