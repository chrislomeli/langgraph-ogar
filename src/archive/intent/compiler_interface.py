"""
Compiler interface boundary: PlanBundle → Composition IR.

This module defines the stable API contracts between the planning layer
and the compilation layer. Implementations live in separate modules
(e.g., compiler.py) and can be swapped without affecting upstream code.

Contracts:
- CompileResult: the output of compilation (CompositionSpec + SectionSpecs + metadata)
- CompileOptions: knobs for regeneration scope, determinism, validation
- PlanCompiler (ABC): the interface any compiler must implement
- IREditor (ABC): the interface for surgical IR-level edits (stubbed)
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional, Set

from symbolic_music.domain import CompositionSpec, SectionSpec

from intent.plan_models import PlanBundle, IRRefinementRequest
from intent.sketch_models import Sketch


# ============================================================================
# Compile options — knobs for the compilation pass
# ============================================================================

@dataclass(frozen=True)
class CompileOptions:
    """
    Options that affect compilation / re-generation behavior.

    Attributes:
        regenerate_voices: If set, only regenerate these voice_ids.
            All other voices are preserved from the previous CompileResult.
        regenerate_sections: If set, only regenerate these section_ids.
        seed: Random seed for deterministic output.
        fail_on_warnings: If true, treat validation warnings as errors.
    """
    regenerate_voices: Optional[Set[str]] = None
    regenerate_sections: Optional[Set[str]] = None
    seed: Optional[int] = None
    fail_on_warnings: bool = False


# ============================================================================
# Compile result — the output of compilation
# ============================================================================

@dataclass(frozen=True)
class CompileResult:
    """
    The complete output of a compilation pass.

    Attributes:
        composition: The top-level CompositionSpec (tracks, meter, tempo).
        sections: All generated SectionSpecs, keyed by a synthetic section
            version ID. These are the content that TrackSpec.placements
            reference via section_version_id.
        warnings: Non-fatal issues encountered during compilation.
        plan_bundle_id: The PlanBundle that produced this result (lineage).
    """
    composition: CompositionSpec
    sections: dict[str, SectionSpec] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    plan_bundle_id: Optional[str] = None


# ============================================================================
# Compiler interface (ABC)
# ============================================================================

class PlanCompiler(abc.ABC):
    """
    Abstract compiler: PlanBundle → CompileResult.

    Implementations:
    - PatternCompiler (rule-based, first implementation)
    - Future: LLM-assisted compiler, hybrid compiler, etc.
    """

    @abc.abstractmethod
    def compile(
        self,
        plan: PlanBundle,
        options: Optional[CompileOptions] = None,
        previous: Optional[CompileResult] = None,
    ) -> CompileResult:
        """
        Compile a PlanBundle into Composition IR.

        Args:
            plan: The fully-resolved PlanBundle.
            options: Compilation options (scoped regeneration, seed, etc.).
            previous: If doing scoped regeneration, the previous result
                to preserve unchanged voices/sections from.

        Returns:
            CompileResult with CompositionSpec + SectionSpecs.
        """
        ...


# ============================================================================
# IR Editor interface (ABC) — stubbed for future implementation
# ============================================================================

class IREditor(abc.ABC):
    """
    Abstract IR editor: surgical edits to compiled output.

    This handles IR-level refinements — direct note/measure/section edits
    that don't go through the plan layer. Stubbed as a clean contract;
    implementation deferred.

    Examples of IR-level edits:
    - "Change bar 7 beat 3 to C minor chord"
    - "Make the bass line in the verse more syncopated"
    - "Add a fill in bar 16"
    """

    @abc.abstractmethod
    def apply(
        self,
        result: CompileResult,
        request: IRRefinementRequest,
    ) -> CompileResult:
        """
        Apply an IR-level refinement to an existing CompileResult.

        Args:
            result: The current compiled output.
            request: What the user wants changed at the note level.

        Returns:
            A new CompileResult with the edits applied.
        """
        ...
