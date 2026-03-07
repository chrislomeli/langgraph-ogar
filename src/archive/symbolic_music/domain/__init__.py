"""
Domain models for symbolic music.

Pure business logic - NO persistence, NO serialization, NO infrastructure.
"""

from symbolic_music.domain.errors import (
    DomainError,
    InvalidPitchError,
    InvalidTimeSignatureError,
    TimeBoundsError,
)
from symbolic_music.domain.models import (
    AnyEvent,
    ChordEvent,
    CompositionSpec,
    MeasureSpec,
    MeterChange,
    MeterMap,
    MetaEvent,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    RT_EIGHTH,
    RT_HALF,
    RT_ONE,
    RT_QUARTER,
    RT_ZERO,
    SectionPlacement,
    SectionSpec,
    TempoChange,
    TempoMap,
    TempoValue,
    TimeSignature,
    TrackConfig,
    TrackSpec,
)

__all__ = [
    # Errors
    "DomainError",
    "TimeBoundsError",
    "InvalidPitchError",
    "InvalidTimeSignatureError",
    # Time
    "RationalTime",
    "RT_ZERO",
    "RT_ONE",
    "RT_QUARTER",
    "RT_HALF",
    "RT_EIGHTH",
    # Pitch
    "Pitch",
    # Time Signature
    "TimeSignature",
    # Events
    "NoteEvent",
    "RestEvent",
    "ChordEvent",
    "MetaEvent",
    "AnyEvent",
    # Containers
    "MeasureSpec",
    "SectionSpec",
    # Timeline
    "MeterChange",
    "MeterMap",
    "TempoChange",
    "TempoMap",
    "TempoValue",
    # Track/Composition
    "TrackConfig",
    "SectionPlacement",
    "TrackSpec",
    "CompositionSpec",
]
