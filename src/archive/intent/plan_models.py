"""
Planning artifacts: the fully-resolved decisions that bridge Sketch → Composition IR.

Design principles:
- This is the AI's output, not the user's input.
- Every field must be precise enough for a compiler to execute deterministically.
- Enum-heavy, validated, lockable — the contract the compiler reads.
- Supports scoped regeneration: unlock one sub-plan, re-plan, recompile.
- Includes refinement protocol for plan-level tweaks.

Assumes Pydantic v2.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Sequence, Set

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ============================================================================
# Enums — musical vocabulary for planning
# ============================================================================

class EnergyLevel(str, Enum):
    very_low = "very_low"
    low = "low"
    medium = "medium"
    high = "high"
    very_high = "very_high"


class DensityLevel(str, Enum):
    sparse = "sparse"
    medium = "medium"
    busy = "busy"


class RegisterBand(str, Enum):
    low = "low"
    mid = "mid"
    high = "high"
    full = "full"


class GrooveFeel(str, Enum):
    straight = "straight"
    swing = "swing"
    halftime = "halftime"
    doubletime = "doubletime"
    shuffle = "shuffle"
    bossa = "bossa"
    samba = "samba"
    clave_2_3 = "clave_2_3"
    clave_3_2 = "clave_3_2"


class SectionRole(str, Enum):
    intro = "intro"
    verse = "verse"
    prechorus = "prechorus"
    chorus = "chorus"
    bridge = "bridge"
    breakdown = "breakdown"
    solo = "solo"
    interlude = "interlude"
    outro = "outro"


class VoiceRole(str, Enum):
    drums = "drums"
    percussion = "percussion"
    bass = "bass"
    rhythm_guitar = "rhythm_guitar"
    lead_guitar = "lead_guitar"
    acoustic_guitar = "acoustic_guitar"
    keys = "keys"
    pad = "pad"
    strings = "strings"
    brass = "brass"
    woodwinds = "woodwinds"
    vox_lead = "vox_lead"
    vox_harmony = "vox_harmony"
    fx = "fx"


class ChordQuality(str, Enum):
    maj = "maj"
    min = "min"
    dim = "dim"
    aug = "aug"
    dom7 = "dom7"
    maj7 = "maj7"
    min7 = "min7"
    min_maj7 = "min_maj7"
    dim7 = "dim7"
    half_dim7 = "half_dim7"
    aug7 = "aug7"
    sus2 = "sus2"
    sus4 = "sus4"
    power = "power"


# ============================================================================
# Voice Plan — the DAW-stable track roster
# ============================================================================

class VoiceSpec(BaseModel):
    """
    A concrete voice/track in the arrangement.

    Maps to the domain's TrackSpec + TrackConfig at compile time.
    voice_id is stable across regenerations — the DAW track doesn't move.
    """
    model_config = ConfigDict(frozen=True)

    voice_id: str = Field(..., min_length=1, description="Stable ID, survives regeneration.")
    name: str = Field(..., min_length=1, description="DAW-friendly display name.")
    role: VoiceRole

    instrument: str = Field(
        ...,
        min_length=1,
        description="Instrument identifier, e.g. 'piano', 'electric_bass', 'drum_kit'.",
    )
    midi_channel: Optional[int] = Field(default=None, ge=1, le=16)
    clef: Optional[Literal["treble", "bass", "alto", "tenor"]] = None

    register_band: RegisterBand = RegisterBand.full
    default_density: DensityLevel = DensityLevel.medium

    # Section participation masks
    only_sections: Sequence[str] = Field(
        default_factory=list,
        description="If non-empty, voice is active only in these section_ids.",
    )
    mute_sections: Sequence[str] = Field(
        default_factory=list,
        description="If non-empty, voice is muted in these section_ids.",
    )

    notes: Optional[str] = Field(
        default=None,
        description="Generation guidance, e.g. 'walking bass in the verse, pedal tone in chorus'.",
    )

    @model_validator(mode="after")
    def _validate_section_masks(self):
        if self.only_sections and self.mute_sections:
            overlap = set(self.only_sections) & set(self.mute_sections)
            if overlap:
                raise ValueError(f"Section mask overlap: {sorted(overlap)}")
        return self


class VoicePlan(BaseModel):
    """The complete voice roster. Lockable for regeneration stability."""
    model_config = ConfigDict(frozen=True)

    voices: tuple[VoiceSpec, ...] = Field(..., min_length=1)
    locked: bool = Field(
        default=False,
        description="If true, voice list must not change during regeneration.",
    )

    @model_validator(mode="after")
    def _validate_unique_ids(self):
        ids = [v.voice_id for v in self.voices]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate voice_id in VoicePlan")
        return self

    def get_voice(self, voice_id: str) -> Optional[VoiceSpec]:
        for v in self.voices:
            if v.voice_id == voice_id:
                return v
        return None

    def voices_for_section(self, section_id: str) -> tuple[VoiceSpec, ...]:
        """Return voices that are active in a given section."""
        result = []
        for v in self.voices:
            if v.mute_sections and section_id in v.mute_sections:
                continue
            if v.only_sections and section_id not in v.only_sections:
                continue
            result.append(v)
        return tuple(result)


# ============================================================================
# Form Plan — song structure
# ============================================================================

class SectionPlan(BaseModel):
    """A planned section: what it is, how long, what it feels like."""
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(..., min_length=1, description="Stable ID, e.g. 'verse1', 'chorus'.")
    role: SectionRole
    bars: int = Field(..., ge=1, le=512)

    time_signature: str = Field(default="4/4", description="e.g. '4/4', '3/4', '6/8'.")
    tempo_bpm: Optional[float] = Field(default=None, ge=20, le=300, description="Override tempo for this section.")

    energy: EnergyLevel = EnergyLevel.medium
    density: DensityLevel = DensityLevel.medium

    notes: Optional[str] = Field(default=None, description="Generation guidance for this section.")


class TimelinePlacement(BaseModel):
    """Places a planned section onto the global bar timeline."""
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(..., min_length=1)
    start_bar: int = Field(..., ge=1)
    repeats: int = Field(default=1, ge=1, le=128)


class FormPlan(BaseModel):
    """Song form: section definitions + their arrangement on the timeline."""
    model_config = ConfigDict(frozen=True)

    sections: tuple[SectionPlan, ...] = Field(..., min_length=1)
    timeline: tuple[TimelinePlacement, ...] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_refs(self):
        defined = {s.section_id for s in self.sections}
        for t in self.timeline:
            if t.section_id not in defined:
                raise ValueError(f"Timeline references undefined section_id: {t.section_id}")
        return self

    @model_validator(mode="after")
    def _validate_unique_section_ids(self):
        ids = [s.section_id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate section_id in FormPlan")
        return self

    def get_section(self, section_id: str) -> Optional[SectionPlan]:
        for s in self.sections:
            if s.section_id == section_id:
                return s
        return None

    def total_bars(self) -> int:
        """Calculate total bars from timeline placements."""
        if not self.timeline:
            return 0
        max_end = 0
        section_map = {s.section_id: s for s in self.sections}
        for tp in self.timeline:
            sp = section_map.get(tp.section_id)
            if sp:
                end = tp.start_bar + (sp.bars * tp.repeats) - 1
                max_end = max(max_end, end)
        return max_end


# ============================================================================
# Harmony Plan — chord progressions per section
# ============================================================================

class ChordEvent(BaseModel):
    """A chord at a specific position within a section."""
    model_config = ConfigDict(frozen=True)

    at_bar: int = Field(..., ge=1, description="Bar number within the section (1-indexed).")
    at_beat: float = Field(default=1.0, ge=1.0, description="Beat within the bar (1-indexed).")
    root: str = Field(..., min_length=1, description="Root note name, e.g. 'C', 'F#', 'Bb'.")
    quality: ChordQuality = ChordQuality.maj
    bass_note: Optional[str] = Field(default=None, description="Slash chord bass, e.g. 'E' for C/E.")

    @property
    def symbol(self) -> str:
        """Human-readable chord symbol."""
        base = f"{self.root}{self.quality.value}"
        if self.bass_note:
            return f"{base}/{self.bass_note}"
        return base


class HarmonySectionPlan(BaseModel):
    """Harmony for one section."""
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1, description="Key for this section, e.g. 'A minor', 'C major'.")
    chords: tuple[ChordEvent, ...] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _validate_chord_order(self):
        for i in range(1, len(self.chords)):
            prev = (self.chords[i - 1].at_bar, self.chords[i - 1].at_beat)
            curr = (self.chords[i].at_bar, self.chords[i].at_beat)
            if curr <= prev:
                raise ValueError("Chords must be in strictly increasing bar/beat order")
        return self


class HarmonyPlan(BaseModel):
    """Harmony across the entire form."""
    model_config = ConfigDict(frozen=True)

    sections: tuple[HarmonySectionPlan, ...] = Field(..., min_length=1)

    def get_section(self, section_id: str) -> Optional[HarmonySectionPlan]:
        for s in self.sections:
            if s.section_id == section_id:
                return s
        return None


# ============================================================================
# Groove Plan — rhythmic feel and percussion strategy
# ============================================================================

class GrooveSectionPlan(BaseModel):
    """Groove parameters for one section."""
    model_config = ConfigDict(frozen=True)

    section_id: str = Field(..., min_length=1)
    feel: GrooveFeel = GrooveFeel.straight

    drum_density: DensityLevel = DensityLevel.medium
    perc_density: DensityLevel = DensityLevel.sparse
    bass_approach: Optional[str] = Field(
        default=None,
        description="e.g. 'root-fifth', 'walking', 'pedal', 'syncopated'.",
    )

    swing_amount: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="0.0 = straight, 1.0 = full triplet swing.",
    )
    humanize_timing_ms: int = Field(default=0, ge=0, le=50)
    humanize_velocity: int = Field(default=0, ge=0, le=30)

    notes: Optional[str] = Field(default=None, description="Free-form groove guidance.")


class GroovePlan(BaseModel):
    """Groove across the entire form."""
    model_config = ConfigDict(frozen=True)

    global_feel: GrooveFeel = GrooveFeel.straight
    sections: tuple[GrooveSectionPlan, ...] = Field(..., min_length=1)

    def get_section(self, section_id: str) -> Optional[GrooveSectionPlan]:
        for s in self.sections:
            if s.section_id == section_id:
                return s
        return None


# ============================================================================
# Render Plan — export preferences (non-musical)
# ============================================================================

class RenderTarget(str, Enum):
    music21 = "music21"
    midi1 = "midi1"
    midi2 = "midi2"


class RenderPlan(BaseModel):
    """Non-musical export preferences."""
    model_config = ConfigDict(frozen=True)

    targets: tuple[RenderTarget, ...] = Field(
        default=(RenderTarget.music21, RenderTarget.midi1),
    )
    midi_file_name: Optional[str] = None
    normalize_track_names: bool = True
    include_section_markers: bool = True


# ============================================================================
# Plan Bundle — the complete planning output
# ============================================================================

class PlanBundle(BaseModel):
    """
    The complete, resolved plan that bridges Sketch → Composition IR.

    This is the checkpoint artifact:
    - AI produces it from a Sketch.
    - User reviews and optionally locks sub-plans.
    - Compiler reads it to produce CompositionSpec + SectionSpecs.
    - Stored in Memgraph with lineage edges to Sketch and Composition versions.
    """
    model_config = ConfigDict(frozen=True)

    bundle_id: Optional[str] = Field(
        default=None,
        description="Stable ID for versioning/storage.",
    )
    sketch_id: Optional[str] = Field(
        default=None,
        description="Link to the Sketch that produced this plan.",
    )

    # --- Global musical parameters ---
    title: str = Field(..., min_length=1)
    key: str = Field(..., min_length=1, description="Global key, e.g. 'A minor'.")
    tempo_bpm: float = Field(..., ge=20, le=300)
    time_signature: str = Field(default="4/4")

    # --- Sub-plans ---
    voice_plan: VoicePlan
    form_plan: FormPlan
    harmony_plan: HarmonyPlan
    groove_plan: GroovePlan
    render_plan: RenderPlan = Field(default_factory=RenderPlan)

    @model_validator(mode="after")
    def _validate_section_coverage(self):
        """Ensure harmony and groove plans cover all form sections."""
        form_ids = {s.section_id for s in self.form_plan.sections}
        harmony_ids = {s.section_id for s in self.harmony_plan.sections}
        groove_ids = {s.section_id for s in self.groove_plan.sections}

        missing_harmony = form_ids - harmony_ids
        if missing_harmony:
            raise ValueError(f"HarmonyPlan missing sections: {sorted(missing_harmony)}")

        missing_groove = form_ids - groove_ids
        if missing_groove:
            raise ValueError(f"GroovePlan missing sections: {sorted(missing_groove)}")

        return self


# ============================================================================
# Refinement Protocol — plan-level tweaks
# ============================================================================

class RefinementScope(str, Enum):
    """What part of the plan a refinement targets."""
    voice_plan = "voice_plan"
    form_plan = "form_plan"
    harmony_plan = "harmony_plan"
    groove_plan = "groove_plan"
    render_plan = "render_plan"
    full = "full"


class RefinementRequest(BaseModel):
    """
    A user's request to modify an existing plan.

    The engine interprets this and produces a new PlanBundle version.
    The prompt is free text; scope hints help the engine focus.

    Examples:
        >>> RefinementRequest(
        ...     prompt="Add a bridge after the second chorus",
        ...     scope={RefinementScope.form_plan},
        ... )

        >>> RefinementRequest(
        ...     prompt="Make the drums busier in the chorus, add congas",
        ...     scope={RefinementScope.groove_plan, RefinementScope.voice_plan},
        ... )

        >>> RefinementRequest(
        ...     prompt="Change the chorus chords to minor",
        ...     scope={RefinementScope.harmony_plan},
        ...     target_sections={"chorus"},
        ... )
    """

    prompt: str = Field(..., min_length=1, description="What the user wants changed.")

    scope: Set[RefinementScope] = Field(
        default_factory=lambda: {RefinementScope.full},
        description="Which sub-plans this refinement may affect.",
    )
    target_sections: Set[str] = Field(
        default_factory=set,
        description="If non-empty, limit changes to these section_ids.",
    )
    target_voices: Set[str] = Field(
        default_factory=set,
        description="If non-empty, limit changes to these voice_ids.",
    )

    # Lineage
    source_bundle_id: Optional[str] = Field(
        default=None,
        description="The PlanBundle being refined.",
    )


class IRRefinementRequest(BaseModel):
    """
    A request to modify the compiled IR directly (surgical note-level edits).

    Stubbed as a clean contract — implementation deferred.
    The compiler or a dedicated IR-editor agent handles these.

    Examples:
        >>> IRRefinementRequest(
        ...     prompt="Change bar 7 beat 3 to C minor chord",
        ...     target_sections={"chorus"},
        ...     target_voices={"keys"},
        ...     target_bars=(7, 7),
        ... )
    """

    prompt: str = Field(..., min_length=1)

    target_sections: Set[str] = Field(default_factory=set)
    target_voices: Set[str] = Field(default_factory=set)
    target_bars: Optional[tuple[int, int]] = Field(
        default=None,
        description="Bar range (inclusive) to constrain the edit, e.g. (7, 12).",
    )

    source_composition_id: Optional[str] = Field(
        default=None,
        description="The CompositionVersion being edited.",
    )
