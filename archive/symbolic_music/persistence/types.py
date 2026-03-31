"""
Type definitions for persistence layer.

TypedDict classes for database row results, providing:
- IDE autocompletion
- Static type checking with mypy
- Documentation of expected row shapes
"""

from typing import TypedDict


# =============================================================================
# Composition Queries
# =============================================================================

class CompositionRow(TypedDict):
    """Row from composition lookup query."""
    cid: str
    title: str
    cvid: str


# =============================================================================
# Timeline Queries
# =============================================================================

class MeterMapChangeRow(TypedDict):
    """Row from meter map query."""
    meter_vid: str
    at_bar: int | None
    i: int | None
    ts_num: int | None
    ts_den: int | None


class TempoMapChangeRow(TypedDict):
    """Row from tempo map query."""
    tempo_vid: str
    at_bar: int | None
    at_beat: int | None
    i: int | None
    bpm_n: int | None
    bpm_d: int | None
    beat_unit_den: int | None


# =============================================================================
# Track Queries
# =============================================================================

class TrackRow(TypedDict):
    """Row from track query."""
    tvid: str
    track_id: str
    name: str | None
    instrument_hint: str | None
    midi_channel: int | None
    clef: str | None
    transposition_semitones: int | None


class PlacementRow(TypedDict):
    """Row from track placement query."""
    svid: str
    start_bar: int
    ordinal: int
    repeats: int | None
    transpose_semitones: int | None
    role: str | None
    gain_db: float | None


# =============================================================================
# Section Queries
# =============================================================================

class SectionRow(TypedDict):
    """Row from section query."""
    svid: str
    name: str | None


class MeasureRow(TypedDict):
    """Row from measure query."""
    mvid: str
    local_ts_num: int | None
    local_ts_den: int | None
    i: int


# =============================================================================
# Event Queries
# =============================================================================

class EventRow(TypedDict):
    """Row from event query (denormalized with pitches/articulations)."""
    evid: str
    kind: str
    offset_n: int
    offset_d: int
    dur_n: int
    dur_d: int
    velocity: int | None
    tie: str | None
    meta_type: str | None
    event_i: int
    pitch_i: int | None
    midi: int | None
    cents_n: int | None
    cents_d: int | None
    spelling_hint: str | None
    artic_i: int | None
    artic_name: str | None
    lyric_text: str | None


# =============================================================================
# Internal Data Structures
# =============================================================================

class PitchData(TypedDict):
    """Pitch data extracted from event rows."""
    i: int | None
    midi: int
    cents_n: int | None
    cents_d: int | None
    spelling_hint: str | None


class EventData(TypedDict):
    """Aggregated event data from multiple rows."""
    kind: str
    offset_n: int
    offset_d: int
    dur_n: int
    dur_d: int
    velocity: int | None
    tie: str | None
    meta_type: str | None
    event_i: int
    pitches: list[PitchData]
    articulations: list[str]
    lyric: str | None
