"""
Domain models for musical content.

Pure business logic - NO persistence, NO serialization, NO infrastructure.

Design principles:
- Immutable value objects
- Rich behavior and domain operations
- Validation at construction (invalid objects cannot exist)
- Type-safe and expressive
- Storage-agnostic
"""

from __future__ import annotations

from fractions import Fraction
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from symbolic_music.domain.errors import (
    DomainError,
    InvalidPitchError,
    InvalidTimeSignatureError,
    TimeBoundsError,
)


# =============================================================================
# RationalTime - Exact Musical Time
# =============================================================================

class RationalTime(BaseModel):
    """
    Exact rational number for musical time values.
    
    Represents offsets, durations, and other time quantities as reduced fractions.
    
    Invariants:
    - denominator > 0
    - gcd-reduced (automatically normalized)
    - numerator can be negative (for some contexts)
    
    Examples:
        >>> quarter_note = RationalTime(n=1, d=4)
        >>> half_note = RationalTime(n=1, d=2)
        >>> dotted_quarter = RationalTime(n=3, d=8)
        >>> RationalTime(n=2, d=4)  # Auto-reduces to 1/2
    """
    
    model_config = ConfigDict(frozen=True)
    
    n: int = Field(..., description="Numerator")
    d: int = Field(..., description="Denominator (must be positive)")
    
    @model_validator(mode="after")
    def _normalize(self) -> "RationalTime":
        """Normalize sign and reduce to lowest terms."""
        if self.d == 0:
            raise DomainError("RationalTime denominator cannot be 0")
        
        # Normalize sign to numerator
        if self.d < 0:
            object.__setattr__(self, "n", -self.n)
            object.__setattr__(self, "d", -self.d)
        
        # Reduce to lowest terms
        frac = Fraction(self.n, self.d)
        object.__setattr__(self, "n", frac.numerator)
        object.__setattr__(self, "d", frac.denominator)
        
        return self
    
    # Factory methods
    
    @staticmethod
    def from_fraction(f: Fraction) -> "RationalTime":
        """Create from Python Fraction."""
        return RationalTime(n=f.numerator, d=f.denominator)
    
    @staticmethod
    def from_int(i: int) -> "RationalTime":
        """Create from integer (whole notes)."""
        return RationalTime(n=i, d=1)
    
    @staticmethod
    def parse(s: str) -> "RationalTime":
        """
        Parse from string: "3/2", "-1/4", "7"
        """
        s = s.strip()
        if "/" in s:
            num_str, den_str = s.split("/", 1)
            return RationalTime(n=int(num_str.strip()), d=int(den_str.strip()))
        return RationalTime(n=int(s), d=1)
    
    # Conversion
    
    def as_fraction(self) -> Fraction:
        """Convert to Python Fraction."""
        return Fraction(self.n, self.d)
    
    def as_float(self) -> float:
        """Convert to float (loses exactness)."""
        return self.n / self.d
    
    # Arithmetic
    
    def __add__(self, other: "RationalTime") -> "RationalTime":
        return RationalTime.from_fraction(self.as_fraction() + other.as_fraction())
    
    def __sub__(self, other: "RationalTime") -> "RationalTime":
        return RationalTime.from_fraction(self.as_fraction() - other.as_fraction())
    
    def __mul__(self, scalar: int | "RationalTime") -> "RationalTime":
        if isinstance(scalar, int):
            return RationalTime.from_fraction(self.as_fraction() * scalar)
        return RationalTime.from_fraction(self.as_fraction() * scalar.as_fraction())
    
    def __truediv__(self, scalar: int | "RationalTime") -> "RationalTime":
        if isinstance(scalar, int):
            if scalar == 0:
                raise ZeroDivisionError()
            return RationalTime.from_fraction(self.as_fraction() / scalar)
        if scalar.n == 0:
            raise ZeroDivisionError()
        return RationalTime.from_fraction(self.as_fraction() / scalar.as_fraction())
    
    def __neg__(self) -> "RationalTime":
        return RationalTime(n=-self.n, d=self.d)
    
    # Comparison
    
    def __lt__(self, other: "RationalTime") -> bool:
        return self.as_fraction() < other.as_fraction()
    
    def __le__(self, other: "RationalTime") -> bool:
        return self.as_fraction() <= other.as_fraction()
    
    def __gt__(self, other: "RationalTime") -> bool:
        return self.as_fraction() > other.as_fraction()
    
    def __ge__(self, other: "RationalTime") -> bool:
        return self.as_fraction() >= other.as_fraction()
    
    def __str__(self) -> str:
        return f"{self.n}/{self.d}" if self.d != 1 else str(self.n)
    
    def __repr__(self) -> str:
        return f"RationalTime({self.n}, {self.d})"


# Constants
RT_ZERO = RationalTime(n=0, d=1)
RT_ONE = RationalTime(n=1, d=1)
RT_QUARTER = RationalTime(n=1, d=4)
RT_HALF = RationalTime(n=1, d=2)
RT_EIGHTH = RationalTime(n=1, d=8)


# =============================================================================
# Pitch - Musical Pitch Representation
# =============================================================================

class Pitch(BaseModel):
    """
    Canonical pitch representation.
    
    Core identity:
    - midi: integer MIDI note number (0..127)
    - cents: optional microtonal offset (100 cents = 1 semitone)
    
    Optional notation hint:
    - spelling_hint: e.g. "C#4" or "Db4" (does NOT affect pitch identity)
    
    Examples:
        >>> middle_c = Pitch(midi=60)
        >>> c_sharp = Pitch(midi=61, spelling_hint="C#4")
        >>> quarter_sharp = Pitch(midi=60, cents=RationalTime(50, 1))
    """
    
    model_config = ConfigDict(frozen=True)
    
    midi: int = Field(..., ge=0, le=127)
    cents: Optional[RationalTime] = None
    spelling_hint: Optional[str] = Field(default=None, exclude=True)
    
    @field_validator("spelling_hint")
    @classmethod
    def _validate_spelling_hint(cls, v: Optional[str]) -> Optional[str]:
        if v is None or not v.strip():
            return None
        return v.strip()
    
    def __eq__(self, other: object) -> bool:
        """Pitches equal if midi and cents match (spelling ignored)."""
        if not isinstance(other, Pitch):
            return NotImplemented
        return self.midi == other.midi and self.cents == other.cents
    
    def __hash__(self) -> int:
        cents_key = (self.cents.n, self.cents.d) if self.cents else None
        return hash((self.midi, cents_key))
    
    def __lt__(self, other: "Pitch") -> bool:
        if self.midi != other.midi:
            return self.midi < other.midi
        self_cents = self.cents or RT_ZERO
        other_cents = other.cents or RT_ZERO
        return self_cents < other_cents
    
    def transpose(self, semitones: int) -> "Pitch":
        """Transpose by semitones, preserving microtonal offset."""
        new_midi = self.midi + semitones
        if not (0 <= new_midi <= 127):
            raise InvalidPitchError(f"Transposition to MIDI {new_midi} out of range")
        return Pitch(midi=new_midi, cents=self.cents, spelling_hint=None)
    
    def frequency_hz(self, a4_hz: float = 440.0) -> float:
        """Calculate frequency in Hz (equal temperament, A4=440)."""
        cents_offset = self.cents.as_float() if self.cents else 0.0
        semitones_from_a4 = (self.midi - 69) + (cents_offset / 100.0)
        return a4_hz * (2 ** (semitones_from_a4 / 12.0))
    
    def __str__(self) -> str:
        base = self.spelling_hint or f"MIDI{self.midi}"
        if self.cents and self.cents != RT_ZERO:
            return f"{base}{self.cents:+}¢"
        return base


# =============================================================================
# TimeSignature
# =============================================================================

class TimeSignature(BaseModel):
    """
    Time signature (meter): num/den (e.g. 4/4, 3/4, 6/8)
    
    Invariants:
    - num >= 1
    - den must be power of 2
    """
    
    model_config = ConfigDict(frozen=True)
    
    num: int = Field(..., ge=1)
    den: int = Field(...)
    
    @field_validator("den")
    @classmethod
    def _validate_den(cls, den: int) -> int:
        if den <= 0:
            raise InvalidTimeSignatureError("Denominator must be positive")
        if den & (den - 1) != 0:
            raise InvalidTimeSignatureError("Denominator must be power of 2")
        return den
    
    def measure_length_quarters(self) -> RationalTime:
        """Measure length in quarter notes: num * (4/den)"""
        return RationalTime.from_fraction(Fraction(self.num, 1) * Fraction(4, self.den))
    
    def __str__(self) -> str:
        return f"{self.num}/{self.den}"


# =============================================================================
# MeterMap - Composition Timeline
# =============================================================================

class MeterChange(BaseModel):
    """A meter change at a specific bar."""
    model_config = ConfigDict(frozen=True)
    
    at_bar: int = Field(..., ge=1)
    ts: TimeSignature


class MeterMap(BaseModel):
    """
    Composition-level meter map.
    
    Invariants:
    - Starts at bar 1
    - Changes strictly increasing
    """
    model_config = ConfigDict(frozen=True)
    
    changes: tuple[MeterChange, ...] = Field(..., min_length=1)
    
    @model_validator(mode="after")
    def _validate(self) -> "MeterMap":
        if self.changes[0].at_bar != 1:
            raise DomainError("MeterMap must start at bar 1")
        
        last_bar = 0
        for ch in self.changes:
            if ch.at_bar <= last_bar:
                raise DomainError("MeterMap changes must be strictly increasing")
            last_bar = ch.at_bar
        return self
    
    def time_signature_at(self, bar: int) -> TimeSignature:
        """Get active time signature at given bar."""
        if bar < 1:
            raise ValueError("Bar must be >= 1")
        
        active = self.changes[0].ts
        for ch in self.changes:
            if ch.at_bar <= bar:
                active = ch.ts
            else:
                break
        return active


# =============================================================================
# TempoMap
# =============================================================================

class TempoValue(BaseModel):
    """Tempo: BPM as exact rational."""
    model_config = ConfigDict(frozen=True)
    
    bpm: RationalTime
    beat_unit_den: int = Field(default=4)
    
    @field_validator("beat_unit_den")
    @classmethod
    def _validate_beat_unit_den(cls, den: int) -> int:
        if den <= 0 or (den & (den - 1) != 0):
            raise DomainError("beat_unit_den must be positive power of 2")
        return den


class TempoChange(BaseModel):
    """A tempo change at bar+beat."""
    model_config = ConfigDict(frozen=True)
    
    at_bar: int = Field(..., ge=1)
    at_beat: int = Field(default=1, ge=1)
    tempo: TempoValue


class TempoMap(BaseModel):
    """
    Composition-level tempo map.
    
    Invariants:
    - Starts at (bar=1, beat=1)
    - Changes strictly increasing
    """
    model_config = ConfigDict(frozen=True)
    
    changes: tuple[TempoChange, ...] = Field(..., min_length=1)
    
    @model_validator(mode="after")
    def _validate(self) -> "TempoMap":
        first = self.changes[0]
        if not (first.at_bar == 1 and first.at_beat == 1):
            raise DomainError("TempoMap must start at bar=1, beat=1")
        
        last = (0, 0)
        for ch in self.changes:
            key = (ch.at_bar, ch.at_beat)
            if key <= last:
                raise DomainError("TempoMap changes must be strictly increasing")
            last = key
        return self
    
    def tempo_at(self, bar: int, beat: int = 1) -> TempoValue:
        """Get active tempo at bar+beat."""
        if bar < 1 or beat < 1:
            raise ValueError("Bar and beat must be >= 1")
        
        active = self.changes[0].tempo
        for ch in self.changes:
            if (ch.at_bar, ch.at_beat) <= (bar, beat):
                active = ch.tempo
            else:
                break
        return active


# =============================================================================
# Events - Musical Content
# =============================================================================

class EventBase(BaseModel):
    """Base for all events with timing validation."""
    model_config = ConfigDict(frozen=True)
    
    offset_q: RationalTime
    dur_q: RationalTime
    
    @model_validator(mode="after")
    def _validate_time(self) -> "EventBase":
        if self.dur_q <= RT_ZERO:
            raise TimeBoundsError("Duration must be > 0")
        if self.offset_q < RT_ZERO:
            raise TimeBoundsError("Offset must be >= 0")
        return self
    
    def end_q(self) -> RationalTime:
        """Calculate end position."""
        return self.offset_q + self.dur_q


class NoteEvent(EventBase):
    """A single note."""
    model_config = ConfigDict(frozen=True)
    
    kind: Literal["note"] = "note"
    pitch: Pitch
    velocity: Optional[int] = Field(default=None, ge=0, le=127)
    tie: Optional[Literal["start", "stop", "continue"]] = None
    articulations: tuple[str, ...] = Field(default=())
    lyric: Optional[str] = None
    
    def transpose(self, semitones: int) -> "NoteEvent":
        """Transpose preserving all attributes."""
        return NoteEvent(
            offset_q=self.offset_q,
            dur_q=self.dur_q,
            pitch=self.pitch.transpose(semitones),
            velocity=self.velocity,
            tie=self.tie,
            articulations=self.articulations,
            lyric=self.lyric,
        )


class RestEvent(EventBase):
    """A rest (silence)."""
    model_config = ConfigDict(frozen=True)
    
    kind: Literal["rest"] = "rest"


class ChordEvent(EventBase):
    """
    Chord (multiple simultaneous pitches).
    
    Invariants:
    - At least 2 pitches
    - Pitches unique and sorted
    """
    model_config = ConfigDict(frozen=True)
    
    kind: Literal["chord"] = "chord"
    pitches: tuple[Pitch, ...] = Field(..., min_length=2)
    velocity: Optional[int] = Field(default=None, ge=0, le=127)
    tie: Optional[Literal["start", "stop", "continue"]] = None
    articulations: tuple[str, ...] = Field(default=())
    lyric: Optional[str] = None
    
    @model_validator(mode="after")
    def _validate_pitches(self) -> "ChordEvent":
        if len(self.pitches) != len(set(self.pitches)):
            raise DomainError("Chord pitches must be unique")
        
        sorted_pitches = tuple(sorted(self.pitches))
        if sorted_pitches != self.pitches:
            object.__setattr__(self, "pitches", sorted_pitches)
        return self
    
    def transpose(self, semitones: int) -> "ChordEvent":
        """Transpose all pitches."""
        return ChordEvent(
            offset_q=self.offset_q,
            dur_q=self.dur_q,
            pitches=tuple(p.transpose(semitones) for p in self.pitches),
            velocity=self.velocity,
            tie=self.tie,
            articulations=self.articulations,
            lyric=self.lyric,
        )


class MetaEvent(EventBase):
    """Meta-events (clef, dynamics, etc.)."""
    model_config = ConfigDict(frozen=True)
    
    kind: Literal["meta"] = "meta"
    meta_type: Literal["clef", "key_signature", "text", "dynamic", "instrument"]
    payload: dict[str, str | int | float] = Field(default_factory=dict)


AnyEvent = Union[NoteEvent, RestEvent, ChordEvent, MetaEvent]


# =============================================================================
# MeasureSpec
# =============================================================================

class MeasureSpec(BaseModel):
    """
    A single measure.
    
    Invariants:
    - Events sorted by (offset, kind, pitch)
    - Events don't exceed measure length (if local_time_signature set)
    """
    model_config = ConfigDict(frozen=True)
    
    local_time_signature: Optional[TimeSignature] = None
    events: tuple[AnyEvent, ...] = Field(default=())
    
    @model_validator(mode="after")
    def _validate_events(self) -> "MeasureSpec":
        # Sort deterministically
        def sort_key(e: AnyEvent) -> tuple:
            offset = (e.offset_q.n, e.offset_q.d)
            kind = e.kind
            
            if isinstance(e, NoteEvent):
                return (offset, kind, e.pitch.midi, e.pitch.cents or RT_ZERO)
            elif isinstance(e, ChordEvent):
                return (offset, kind, min(p.midi for p in e.pitches))
            elif isinstance(e, RestEvent):
                return (offset, kind, 0)
            elif isinstance(e, MetaEvent):
                return (offset, kind, e.meta_type)
            return (offset, kind)
        
        sorted_events = tuple(sorted(self.events, key=sort_key))
        object.__setattr__(self, "events", sorted_events)
        
        # Validate bounds
        if self.local_time_signature:
            ml = self.local_time_signature.measure_length_quarters()
            for e in self.events:
                if e.end_q() > ml:
                    raise TimeBoundsError(f"Event exceeds measure length")
        
        return self


# =============================================================================
# SectionSpec - Reusable Multi-Measure Content
# =============================================================================

class SectionSpec(BaseModel):
    """
    Named, reusable section (Intro, Verse, Chorus, etc.).
    
    Invariants:
    - Name non-empty
    - At least one measure
    """
    model_config = ConfigDict(frozen=True)
    
    name: str
    measures: tuple[MeasureSpec, ...] = Field(..., min_length=1)
    
    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise DomainError("Section name cannot be empty")
        return v


# =============================================================================
# TrackConfig
# =============================================================================

class TrackConfig(BaseModel):
    """Track metadata and routing."""
    model_config = ConfigDict(frozen=True)
    
    name: str
    instrument_hint: Optional[str] = None
    midi_channel: Optional[int] = Field(default=None, ge=1, le=16)
    clef: Optional[Literal["treble", "bass", "alto", "tenor"]] = None
    transposition_semitones: int = 0


# =============================================================================
# SectionPlacement - Arrangement Layer
# =============================================================================

class SectionPlacement(BaseModel):
    """Places a SectionVersion onto a Track."""
    model_config = ConfigDict(frozen=True)
    
    section_version_id: str
    start_bar: int = Field(..., ge=1)
    repeats: int = Field(default=1, ge=1)
    transpose_semitones: int = 0
    role: Optional[str] = None
    gain_db: float = 0.0


# =============================================================================
# TrackSpec
# =============================================================================

class TrackSpec(BaseModel):
    """
    A track (performance lane).
    
    Invariants:
    - Placements sorted by (start_bar, section_version_id)
    """
    model_config = ConfigDict(frozen=True)
    
    track_id: str
    config: TrackConfig
    placements: tuple[SectionPlacement, ...] = Field(default=())
    
    @model_validator(mode="after")
    def _validate(self) -> "TrackSpec":
        sorted_pl = tuple(
            sorted(self.placements, key=lambda p: (p.start_bar, p.section_version_id))
        )
        object.__setattr__(self, "placements", sorted_pl)
        return self


# =============================================================================
# CompositionSpec - Top-Level Work
# =============================================================================

class CompositionSpec(BaseModel):
    """
    Complete musical composition.
    
    Invariants:
    - Title non-empty
    - Track IDs unique
    - Tracks sorted by track_id
    """
    model_config = ConfigDict(frozen=True)
    
    title: str
    meter_map: MeterMap
    tempo_map: TempoMap
    tracks: tuple[TrackSpec, ...] = Field(default=())
    
    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise DomainError("Title cannot be empty")
        return v
    
    @model_validator(mode="after")
    def _validate(self) -> "CompositionSpec":
        # Unique track IDs
        ids = [t.track_id for t in self.tracks]
        if len(ids) != len(set(ids)):
            raise DomainError("Track IDs must be unique")
        
        # Sort tracks
        sorted_tracks = tuple(sorted(self.tracks, key=lambda t: t.track_id))
        object.__setattr__(self, "tracks", sorted_tracks)
        return self
    
    def get_track(self, track_id: str) -> Optional[TrackSpec]:
        """Get track by ID."""
        for t in self.tracks:
            if t.track_id == track_id:
                return t
        return None
