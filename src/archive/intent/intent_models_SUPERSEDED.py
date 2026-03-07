"""
Pydantic models for the Intent → Plan → Composition pipeline.

Design goals:
- MCP-ready: JSON-serializable, versionable contracts
- Architecture-first: explicit artifacts for intent and planning
- IR-agnostic intent; IR-aligned planning
- Deterministic regeneration via stable IDs and explicit scope

Assumes Pydantic v2.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Optional, Sequence

from pydantic import BaseModel, Field, model_validator


# ----------------------------
# Common primitives
# ----------------------------

NonEmptyStr = Annotated[str, Field(min_length=1)]


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


class LatinIntent(str, Enum):
    """
    How 'latin flavor' should behave in the arrangement.
    """
    none = "none"
    seasoning = "seasoning"              # subtle perc + light rhythmic influence
    groove_hybrid = "groove_hybrid"      # groove meaningfully shaped by latin feel
    percussion_forward = "percussion_forward"  # percussion is a core engine


class GrooveFeel(str, Enum):
    """
    High-level feel descriptors. Extend freely.
    """
    straight = "straight"
    swing = "swing"
    halftime = "halftime"
    doubletime = "doubletime"
    bossa_influenced = "bossa_influenced"
    samba_influenced = "samba_influenced"
    clave_2_3 = "clave_2_3"
    clave_3_2 = "clave_3_2"


class ConstraintTag(str, Enum):
    """
    Portable constraints that planners/generators can interpret.
    """
    drum_backbeat_primary = "drum_backbeat_primary"
    no_double_kick = "no_double_kick"
    avoid_batucada = "avoid_batucada"
    keep_melody_intact = "keep_melody_intact"
    prefer_power_chords = "prefer_power_chords"
    avoid_dense_strings = "avoid_dense_strings"
    no_key_change = "no_key_change"


class TimeUnit(str, Enum):
    """
    Aligns with your IR's RationalTime (quarter-note basis).
    """
    quarter_note = "quarter_note"  # offsets/durations expressed in quarter-note units


# ----------------------------
# Seed material
# ----------------------------

class SeedKind(str, Enum):
    melody = "melody"
    motif = "motif"
    rhythm_cell = "rhythm_cell"
    harmony_sketch = "harmony_sketch"


class SeedRef(BaseModel):
    """
    A reference to existing material (e.g., a stored composition/track/section version).
    Keep it generic: the compiler can resolve it to your IR objects.
    """
    kind: SeedKind
    ref_id: NonEmptyStr = Field(description="Opaque reference: composition ID, section version ID, file ID, etc.")
    description: Optional[str] = None
    must_preserve_rhythm: bool = False
    must_preserve_pitches: bool = False


# ----------------------------
# Intent artifact
# ----------------------------

class SectionRole(str, Enum):
    intro = "intro"
    verse = "verse"
    prechorus = "prechorus"
    chorus = "chorus"
    bridge = "bridge"
    breakdown = "breakdown"
    outro = "outro"


class SectionIntent(BaseModel):
    role: SectionRole
    energy: EnergyLevel = EnergyLevel.medium
    density: DensityLevel = DensityLevel.medium
    notes: Optional[str] = Field(default=None, description="Free-form guidance for this section.")


class IntentSpec(BaseModel):
    """
    User-facing goals and constraints. No notes.
    """
    intent_id: Optional[str] = Field(default=None, description="Stable ID if you version/store intents.")
    title_hint: Optional[str] = None

    # Style
    genre_core: NonEmptyStr = Field(description="e.g., 'rock', 'cinematic', 'pop'")
    genre_modifiers: Sequence[str] = Field(default_factory=list, description="e.g., ['latin_flavor', 'hybrid_orchestral']")

    # Latin-specific controls (optional)
    latin_intent: LatinIntent = LatinIntent.none
    latin_rhythm_hint: Optional[str] = Field(
        default=None,
        description="Optional natural-language hint like 'bossa-ish', 'samba-lite', 'rock fusion'.",
    )

    # Global musical constraints
    key_hint: Optional[str] = Field(default=None, description="e.g., 'A minor'. Optional; engine may infer.")
    tempo_bpm_hint: Optional[float] = Field(default=None, ge=20, le=300)
    time_signature_hint: Optional[str] = Field(default=None, description="e.g., '4/4', '6/8'")

    # Track/voice constraints
    min_voices: int = Field(default=4, ge=1, le=64)
    max_voices: int = Field(default=12, ge=1, le=128)
    required_roles: Sequence[str] = Field(default_factory=lambda: ["drums", "bass"])
    allowed_extra_roles: Sequence[str] = Field(default_factory=list)

    # Section-level intent (energy arc, density arc)
    section_intents: Sequence[SectionIntent] = Field(default_factory=list)

    # Constraints and preferences
    constraints: Sequence[ConstraintTag] = Field(default_factory=list)
    freeform_constraints: Sequence[str] = Field(default_factory=list)

    # Seeds
    seeds: Sequence[SeedRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_voice_budget(self):
        if self.min_voices > self.max_voices:
            raise ValueError("min_voices must be <= max_voices")
        return self


# ----------------------------
# Planning artifacts
# ----------------------------

class VoiceRole(str, Enum):
    drums = "drums"
    latin_perc = "latin_perc"
    bass = "bass"
    rhythm_guitar = "rhythm_guitar"
    lead_guitar = "lead_guitar"
    keys = "keys"
    pad = "pad"
    strings = "strings"
    brass = "brass"
    vox = "vox"
    fx = "fx"


class VoiceSpec(BaseModel):
    """
    Concrete track/voice with stable ID.
    Maps naturally to your IR's TrackSpec + TrackConfig.
    """
    voice_id: NonEmptyStr = Field(description="Stable ID; should not change across regenerations.")
    name: NonEmptyStr = Field(description="DAW-friendly track name.")
    role: VoiceRole

    instrument_hint: Optional[str] = Field(default=None, description="e.g., 'bass_guitar', 'piano', 'congas'")
    midi_channel: Optional[int] = Field(default=None, ge=1, le=16)
    clef: Optional[Literal["treble", "bass", "alto", "tenor"]] = None

    register: RegisterBand = RegisterBand.full
    density: DensityLevel = DensityLevel.medium

    # Participation: if empty, assumed "all sections"
    only_sections: Sequence[SectionRole] = Field(default_factory=list, description="If set, voice is active only in these sections.")
    mute_sections: Sequence[SectionRole] = Field(default_factory=list, description="If set, voice is muted in these sections.")

    notes: Optional[str] = Field(default=None, description="Free-form guidance (e.g., 'power chords, palm-muted verse').")

    @model_validator(mode="after")
    def _validate_section_masks(self):
        if self.only_sections and self.mute_sections:
            overlap = set(self.only_sections).intersection(set(self.mute_sections))
            if overlap:
                raise ValueError(f"VoiceSpec section masks overlap: {sorted(overlap)}")
        return self


class VoicePlan(BaseModel):
    """
    The DAW-stable voice list. This should be 'locked' before generation for reproducibility.
    """
    plan_id: Optional[str] = None
    voices: Sequence[VoiceSpec]
    locked: bool = Field(default=False, description="If true, voice list must not change during regeneration.")

    @model_validator(mode="after")
    def _validate_unique_voice_ids(self):
        ids = [v.voice_id for v in self.voices]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate voice_id in VoicePlan")
        return self


class SectionSpecPlan(BaseModel):
    """
    A planned section (not your IR SectionSpec) that describes *what should exist*.
    The compiler will create per-voice sections (often voice-scoped) and placements.
    """
    section_id: NonEmptyStr = Field(description="Stable ID for the section concept, e.g. 'A', 'chorus1'.")
    role: SectionRole
    bars: int = Field(ge=1, le=512)
    time_signature: Optional[str] = Field(default=None, description="Override TS for this section, e.g. '4/4'.")
    tempo_bpm: Optional[float] = Field(default=None, ge=20, le=300)
    energy: Optional[EnergyLevel] = None
    density: Optional[DensityLevel] = None
    notes: Optional[str] = None


class TimelinePlacement(BaseModel):
    """
    Places a planned section onto the global bar timeline.
    Mirrors your IR concept of SectionPlacement(start_bar, repeats).
    """
    section_id: NonEmptyStr
    start_bar: int = Field(ge=1, le=100000)
    repeats: int = Field(default=1, ge=1, le=128)
    notes: Optional[str] = None


class FormPlan(BaseModel):
    """
    Defines the song form as planned sections + timeline placements.
    """
    plan_id: Optional[str] = None
    sections: Sequence[SectionSpecPlan]
    timeline: Sequence[TimelinePlacement]

    @model_validator(mode="after")
    def _validate_refs(self):
        defined = {s.section_id for s in self.sections}
        for t in self.timeline:
            if t.section_id not in defined:
                raise ValueError(f"Timeline refers to undefined section_id: {t.section_id}")
        return self


class ChordQuality(str, Enum):
    maj = "maj"
    min = "min"
    dim = "dim"
    aug = "aug"
    dom7 = "dom7"
    maj7 = "maj7"
    min7 = "min7"
    sus2 = "sus2"
    sus4 = "sus4"


class HarmonyEventPlan(BaseModel):
    """
    A harmony change at a given bar/beat position within a section.
    """
    at_bar: int = Field(ge=1, le=512)
    at_beat: float = Field(ge=1.0, le=64.0)  # simple; compiler can quantize to RationalTime
    symbol: NonEmptyStr = Field(description="Chord symbol or roman numeral, e.g. 'Am', 'V/vi', 'i'.")
    notes: Optional[str] = None


class HarmonySectionPlan(BaseModel):
    section_id: NonEmptyStr
    key_hint: Optional[str] = None
    harmonic_rhythm: Optional[str] = Field(default=None, description="e.g., '1 chord per bar', '2 per bar'")
    events: Sequence[HarmonyEventPlan] = Field(default_factory=list)


class HarmonyPlan(BaseModel):
    """
    Harmony across the form. Storable even if your IR stores only notes for now.
    """
    plan_id: Optional[str] = None
    sections: Sequence[HarmonySectionPlan]


class GrooveSectionPlan(BaseModel):
    section_id: NonEmptyStr
    feel: GrooveFeel = GrooveFeel.straight

    # Drum/bass pocket + intensity controls
    drum_intensity: DensityLevel = DensityLevel.medium
    perc_intensity: DensityLevel = DensityLevel.sparse

    # Humanization targets (compiler/generator interprets)
    timing_humanize_ms: Optional[int] = Field(default=None, ge=0, le=50)
    velocity_humanize: Optional[int] = Field(default=None, ge=0, le=30)

    notes: Optional[str] = Field(default=None, description="e.g., 'rock backbeat, bossa-ish hats, sparse guiro'.")


class GroovePlan(BaseModel):
    plan_id: Optional[str] = None
    latin_intent: LatinIntent = LatinIntent.none
    sections: Sequence[GrooveSectionPlan]


class RenderTarget(str, Enum):
    music21 = "music21"
    midi1 = "midi1"
    midi2 = "midi2"


class RenderPlan(BaseModel):
    """
    Non-musical export preferences.
    """
    targets: Sequence[RenderTarget] = Field(default_factory=lambda: [RenderTarget.music21, RenderTarget.midi1])
    midi_file_name: Optional[str] = None
    normalize_track_names: bool = True
    include_markers: bool = True


class PlanBundle(BaseModel):
    """
    The complete planning output. This is the bridge from Intent to Composition IR.
    """
    bundle_id: Optional[str] = None
    intent_ref_id: Optional[str] = Field(default=None, description="Link to an IntentSpec version ID if stored.")
    voice_plan: VoicePlan
    form_plan: FormPlan
    harmony_plan: HarmonyPlan
    groove_plan: GroovePlan
    render_plan: RenderPlan = Field(default_factory=RenderPlan)
