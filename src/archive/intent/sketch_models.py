"""
User-facing sketch: the loose, conversational input that starts the pipeline.

Design principles:
- Deliberately minimal and forgiving — this is what a human types, not what a compiler reads.
- Free text where possible; light structure only where it genuinely helps the engine.
- Seed material can be references to existing graph objects OR inline note data.
- The engine (LLM or deterministic) is responsible for interpreting this into a PlanBundle.

Assumes Pydantic v2.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Seed material — things the user brings to the table
# ---------------------------------------------------------------------------

class SeedKind(str, Enum):
    """What kind of musical material the seed represents."""
    melody = "melody"
    motif = "motif"
    rhythm_cell = "rhythm_cell"
    harmony_sketch = "harmony_sketch"
    bass_line = "bass_line"
    drum_pattern = "drum_pattern"
    full_section = "full_section"


class SeedRef(BaseModel):
    """
    A reference to existing material stored in the graph.

    The engine resolves this to actual SectionSpec / event data
    via the persistence layer.
    """
    kind: SeedKind
    ref_id: str = Field(
        ...,
        min_length=1,
        description="Graph reference: section_version_id, composition_id, etc.",
    )
    description: Optional[str] = Field(
        default=None,
        description="What this seed is, in the user's words.",
    )
    preserve_rhythm: bool = Field(
        default=False,
        description="Hint: keep the rhythmic shape when adapting this seed.",
    )
    preserve_pitches: bool = Field(
        default=False,
        description="Hint: keep the pitch content when adapting this seed.",
    )


class InlineNoteSpec(BaseModel):
    """
    Lightweight inline note for sketching a melody or motif directly.

    Not a full NoteEvent — just enough for the engine to understand
    the musical idea. The compiler will produce proper domain events.
    """
    midi: int = Field(..., ge=0, le=127, description="MIDI note number.")
    dur: str = Field(
        default="1/4",
        description="Duration as a fraction of a whole note, e.g. '1/4', '1/8', '3/8'.",
    )
    spelling: Optional[str] = Field(
        default=None,
        description="Optional enharmonic hint, e.g. 'C#4', 'Db4'.",
    )


class InlineSeed(BaseModel):
    """
    Inline musical material — the user hums a melody and we capture it
    as a sequence of simple note specs.
    """
    kind: SeedKind = SeedKind.melody
    notes: Sequence[InlineNoteSpec] = Field(..., min_length=1)
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Voice hint — what the user wants in the arrangement
# ---------------------------------------------------------------------------

class VoiceHint(BaseModel):
    """
    A loose voice/instrument suggestion from the user.

    Not a VoiceSpec — the engine decides the final roster.
    """
    name: str = Field(
        ...,
        min_length=1,
        description="Instrument or role name, e.g. 'piano', 'bass', 'drums', 'strings'.",
    )
    importance: Literal["required", "preferred", "optional"] = Field(
        default="preferred",
        description="How strongly the user wants this voice.",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Free-form guidance, e.g. 'palm-muted power chords in the verse'.",
    )


# ---------------------------------------------------------------------------
# The Sketch itself
# ---------------------------------------------------------------------------

class Sketch(BaseModel):
    """
    The user's musical sketch — a structured prompt.

    This is the entry point to the pipeline. Everything here is optional
    except the prompt itself. The engine fills in whatever the user
    leaves out, making musically reasonable defaults.

    Examples:
        >>> Sketch(prompt="Rock tune, bossa groove, A minor, verse-chorus-verse")

        >>> Sketch(
        ...     prompt="Chill jazz ballad, piano trio, build energy into the bridge",
        ...     key="Bb major",
        ...     tempo_bpm=72,
        ...     voice_hints=[
        ...         VoiceHint(name="piano", importance="required"),
        ...         VoiceHint(name="upright bass", importance="required"),
        ...         VoiceHint(name="brushes drums", importance="required"),
        ...     ],
        ... )
    """

    # --- Core: the user's words ---
    prompt: str = Field(
        ...,
        min_length=1,
        description=(
            "Free-text description of the desired music. "
            "Genre, mood, style, structure, energy — whatever the user wants to say."
        ),
    )

    # --- Optional structured hints (engine uses these if present) ---
    title: Optional[str] = Field(
        default=None,
        description="Working title for the composition.",
    )
    key: Optional[str] = Field(
        default=None,
        description="Key hint, e.g. 'A minor', 'Bb major'. Planner infers if absent.",
    )
    tempo_bpm: Optional[float] = Field(
        default=None,
        ge=20,
        le=300,
        description="Tempo hint in BPM. Planner infers from genre if absent.",
    )
    time_signature: Optional[str] = Field(
        default=None,
        description="Time signature hint, e.g. '4/4', '6/8'. Planner infers if absent.",
    )

    # --- Form hint ---
    form_hint: Optional[str] = Field(
        default=None,
        description=(
            "Loose form description: 'verse-chorus-verse', 'AABA', "
            "'intro, verse, chorus, bridge, chorus, outro'. "
            "Free text — the engine parses it."
        ),
    )

    # --- Voice hints ---
    voice_hints: Sequence[VoiceHint] = Field(
        default_factory=list,
        description="Instrument/voice suggestions. Empty = let the engine decide.",
    )

    # --- Exclusions ---
    avoid: Sequence[str] = Field(
        default_factory=list,
        description=(
            "Things to avoid: instruments, styles, techniques. "
            "e.g. ['synths', 'double kick', 'key changes']"
        ),
    )

    # --- Seed material ---
    seed_refs: Sequence[SeedRef] = Field(
        default_factory=list,
        description="References to existing material in the graph.",
    )
    inline_seeds: Sequence[InlineSeed] = Field(
        default_factory=list,
        description="Inline melodic/rhythmic ideas.",
    )

    # --- Sketch identity (for versioning / lineage) ---
    sketch_id: Optional[str] = Field(
        default=None,
        description="Stable ID if this sketch is stored/versioned.",
    )
