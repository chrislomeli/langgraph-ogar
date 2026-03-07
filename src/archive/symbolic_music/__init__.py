"""
Symbolic Music - Graph-based musical composition storage and rendering.

A Python package for storing, versioning, and rendering symbolic music
using a graph database (Memgraph).

Main modules:
- domain: Pure domain models (Pitch, RationalTime, Events, Specs)
- persistence: Graph database read/write operations
- rendering: Output to music21 and other formats
"""

from symbolic_music.domain import (
    ChordEvent,
    CompositionSpec,
    DomainError,
    InvalidPitchError,
    InvalidTimeSignatureError,
    MeasureSpec,
    MeterChange,
    MeterMap,
    MetaEvent,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    SectionPlacement,
    SectionSpec,
    TempoChange,
    TempoMap,
    TempoValue,
    TimeBoundsError,
    TimeSignature,
    TrackConfig,
    TrackSpec,
)

__version__ = "0.1.0"

__all__ = [
    # Domain models
    "RationalTime",
    "Pitch",
    "TimeSignature",
    "NoteEvent",
    "RestEvent",
    "ChordEvent",
    "MetaEvent",
    "MeasureSpec",
    "SectionSpec",
    "MeterChange",
    "MeterMap",
    "TempoChange",
    "TempoMap",
    "TempoValue",
    "TrackConfig",
    "SectionPlacement",
    "TrackSpec",
    "CompositionSpec",
    # Errors
    "DomainError",
    "TimeBoundsError",
    "InvalidPitchError",
    "InvalidTimeSignatureError",
]
