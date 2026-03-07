"""
Graph persistence adapter for domain models.

This is the ONLY module that knows about graph storage.
It translates between pure domain objects and graph representations.

Responsibilities:
- Convert domain objects → graph properties + relationships
- Reconstruct domain objects from graph data  
- Compute content hashes for content-addressing
- Define canonical representations for hashing

Domain models remain completely pure and storage-agnostic.
"""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from symbolic_music.domain import (
    AnyEvent,
    ChordEvent,
    CompositionSpec,
    MeasureSpec,
    MetaEvent,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    RT_ZERO,
    SectionSpec,
    TimeSignature,
    TrackSpec,
)


# =============================================================================
# Content Hashing (for content-addressed storage)
# =============================================================================

def _canonical_value(obj: Any) -> Any:
    """
    Convert to canonical JSON-serializable form.
    
    Rules:
    - Deterministic ordering (sorted dict keys)
    - Type normalization (tuples → lists)
    - No floats (use exact rationals)
    - Domain objects converted via their canonical representation
    """
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    
    if isinstance(obj, float):
        # Convert float to string representation for deterministic hashing
        # This handles gain_db and similar fields
        return str(obj)
    
    if isinstance(obj, dict):
        return {str(k): _canonical_value(v) for k, v in sorted(obj.items())}
    
    if isinstance(obj, (list, tuple)):
        return [_canonical_value(item) for item in obj]
    
    # For domain types, use adapter methods
    if isinstance(obj, RationalTime):
        return RationalTimeAdapter.to_canonical(obj)
    if isinstance(obj, Pitch):
        return PitchAdapter.to_canonical(obj)
    if isinstance(obj, TimeSignature):
        return TimeSignatureAdapter.to_canonical(obj)
    if isinstance(obj, (NoteEvent, RestEvent, ChordEvent, MetaEvent)):
        return EventAdapter.to_canonical(obj)
    if isinstance(obj, MeasureSpec):
        return MeasureAdapter.to_canonical(obj)
    if isinstance(obj, SectionSpec):
        return SectionAdapter.to_canonical(obj)
    if isinstance(obj, TrackSpec):
        return TrackAdapter.to_canonical(obj)
    if isinstance(obj, CompositionSpec):
        return CompositionAdapter.to_canonical(obj)
    
    raise TypeError(f"Cannot canonicalize type: {type(obj)}")


def _stable_json(obj: Any) -> str:
    """Deterministic JSON encoding."""
    canonical = _canonical_value(obj)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def content_hash(obj: Any) -> str:
    """SHA-256 hash of canonical JSON representation."""
    return sha256(_stable_json(obj).encode("utf-8")).hexdigest()


# =============================================================================
# RationalTime Adapter
# =============================================================================

class RationalTimeAdapter:
    """Converts RationalTime to/from graph storage."""
    
    @staticmethod
    def to_properties(rt: RationalTime, prefix: str = "") -> dict[str, int]:
        """
        Convert to graph properties.
        
        Args:
            rt: RationalTime to convert
            prefix: Property name prefix (e.g., "offset_" → "offset_n", "offset_d")
        
        Returns:
            {"<prefix>n": int, "<prefix>d": int}
        """
        return {
            f"{prefix}n": rt.n,
            f"{prefix}d": rt.d,
        }
    
    @staticmethod
    def from_properties(props: dict, prefix: str = "") -> RationalTime:
        """
        Reconstruct from graph properties.
        
        Args:
            props: Properties dict containing "<prefix>n" and "<prefix>d"
            prefix: Property name prefix
        """
        return RationalTime(
            n=props[f"{prefix}n"],
            d=props[f"{prefix}d"],
        )
    
    @staticmethod
    def to_canonical(rt: RationalTime) -> dict:
        """Canonical representation for hashing."""
        return {"n": rt.n, "d": rt.d}


# =============================================================================
# Pitch Adapter
# =============================================================================

class PitchAdapter:
    """Converts Pitch to/from graph storage."""
    
    @staticmethod
    def to_properties(pitch: Pitch) -> dict:
        """
        Convert Pitch to graph node properties.
        
        Returns dict suitable for Pitch node creation.
        """
        props = {
            "midi": pitch.midi,
            "cents_n": pitch.cents.n if pitch.cents else 0,
            "cents_d": pitch.cents.d if pitch.cents else 1,
        }
        
        # spelling_hint is notation-only, not part of musical identity
        if pitch.spelling_hint:
            props["spelling_hint"] = pitch.spelling_hint
        
        return props
    
    @staticmethod
    def from_properties(props: dict) -> Pitch:
        """Reconstruct Pitch from graph node properties."""
        cents = None
        if props.get("cents_n") and props["cents_n"] != 0:
            cents = RationalTime(n=props["cents_n"], d=props["cents_d"])
        
        return Pitch(
            midi=props["midi"],
            cents=cents,
            spelling_hint=props.get("spelling_hint"),
        )
    
    @staticmethod
    def to_canonical(pitch: Pitch) -> dict:
        """Canonical representation (excludes spelling_hint)."""
        result = {"midi": pitch.midi}
        if pitch.cents:
            result["cents"] = RationalTimeAdapter.to_canonical(pitch.cents)
        return result
    
    @staticmethod
    def compute_hash(pitch: Pitch) -> str:
        """Content hash for Pitch (identity-based, excludes spelling)."""
        return content_hash(PitchAdapter.to_canonical(pitch))


# =============================================================================
# TimeSignature Adapter
# =============================================================================

class TimeSignatureAdapter:
    """Converts TimeSignature to/from graph storage."""
    
    @staticmethod
    def to_properties(ts: TimeSignature, prefix: str = "") -> dict:
        """Convert to graph properties."""
        return {
            f"{prefix}num": ts.num,
            f"{prefix}den": ts.den,
        }
    
    @staticmethod
    def from_properties(props: dict, prefix: str = "") -> TimeSignature:
        """Reconstruct from graph properties."""
        return TimeSignature(
            num=props[f"{prefix}num"],
            den=props[f"{prefix}den"],
        )
    
    @staticmethod
    def to_canonical(ts: TimeSignature) -> dict:
        """Canonical representation for hashing."""
        return {"num": ts.num, "den": ts.den}


# =============================================================================
# Event Adapter
# =============================================================================

class EventAdapter:
    """Converts Events to/from graph storage."""
    
    @staticmethod
    def to_properties(event: AnyEvent) -> dict:
        """
        Convert event to graph node properties.
        
        Returns base properties that go on the EventVersion node itself.
        Relationships (pitches, articulations) handled separately.
        """
        props = {
            "kind": event.kind,
            **RationalTimeAdapter.to_properties(event.offset_q, "offset_"),
            **RationalTimeAdapter.to_properties(event.dur_q, "dur_"),
        }
        
        # Add type-specific queryable fields
        if isinstance(event, NoteEvent):
            props["midi"] = event.pitch.midi
            props["midi_min"] = event.pitch.midi
            props["midi_max"] = event.pitch.midi
            if event.velocity is not None:
                props["velocity"] = event.velocity
            if event.tie:
                props["tie"] = event.tie
        
        elif isinstance(event, ChordEvent):
            midis = [p.midi for p in event.pitches]
            props["midi_min"] = min(midis)
            props["midi_max"] = max(midis)
            if event.velocity is not None:
                props["velocity"] = event.velocity
            if event.tie:
                props["tie"] = event.tie
        
        elif isinstance(event, MetaEvent):
            props["meta_type"] = event.meta_type
        
        return props
    
    @staticmethod
    def to_relationships(event: AnyEvent) -> list[tuple[str, dict, dict]]:
        """
        Get relationships to create from this event.
        
        Returns list of (rel_type, target_props, rel_props) tuples.
        """
        rels = []
        
        if isinstance(event, NoteEvent):
            # HAS_PITCH relationship
            pitch_props = PitchAdapter.to_properties(event.pitch)
            pitch_props["content_hash"] = PitchAdapter.compute_hash(event.pitch)
            rels.append(("HAS_PITCH", pitch_props, {"i": 0}))
            
            # Articulations
            for i, artic in enumerate(event.articulations):
                rels.append(("HAS_ARTICULATION", {"name": artic}, {"i": i}))
            
            # Lyric
            if event.lyric:
                rels.append(("HAS_LYRIC", {"text": event.lyric}, {}))
        
        elif isinstance(event, ChordEvent):
            # Multiple HAS_PITCH relationships
            for i, pitch in enumerate(event.pitches):
                pitch_props = PitchAdapter.to_properties(pitch)
                pitch_props["content_hash"] = PitchAdapter.compute_hash(pitch)
                rels.append(("HAS_PITCH", pitch_props, {"i": i}))
            
            # Articulations
            for i, artic in enumerate(event.articulations):
                rels.append(("HAS_ARTICULATION", {"name": artic}, {"i": i}))
            
            # Lyric
            if event.lyric:
                rels.append(("HAS_LYRIC", {"text": event.lyric}, {}))
        
        elif isinstance(event, MetaEvent):
            # Payload as relationship
            if event.payload:
                rels.append(("HAS_PAYLOAD", event.payload, {}))
        
        return rels
    
    @staticmethod
    def from_graph(node_props: dict, related: dict) -> AnyEvent:
        """
        Reconstruct Event from graph data.
        
        Args:
            node_props: EventVersion node properties
            related: Dict of related data:
                {"pitches": [...], "articulations": [...], "lyric": {...}}
        """
        offset_q = RationalTimeAdapter.from_properties(node_props, "offset_")
        dur_q = RationalTimeAdapter.from_properties(node_props, "dur_")
        kind = node_props["kind"]
        
        if kind == "note":
            pitch_data = related["pitches"][0]
            pitch = PitchAdapter.from_properties(pitch_data)
            
            articulations = tuple(
                a["name"]
                for a in sorted(related.get("articulations", []), key=lambda x: x.get("i", 0))
            )
            
            return NoteEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                pitch=pitch,
                velocity=node_props.get("velocity"),
                tie=node_props.get("tie"),
                articulations=articulations,
                lyric=related.get("lyric", {}).get("text"),
            )
        
        elif kind == "rest":
            return RestEvent(offset_q=offset_q, dur_q=dur_q)
        
        elif kind == "chord":
            pitches = tuple(
                PitchAdapter.from_properties(p)
                for p in sorted(related["pitches"], key=lambda x: x.get("i", 0))
            )
            
            articulations = tuple(
                a["name"]
                for a in sorted(related.get("articulations", []), key=lambda x: x.get("i", 0))
            )
            
            return ChordEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                pitches=pitches,
                velocity=node_props.get("velocity"),
                tie=node_props.get("tie"),
                articulations=articulations,
                lyric=related.get("lyric", {}).get("text"),
            )
        
        elif kind == "meta":
            return MetaEvent(
                offset_q=offset_q,
                dur_q=dur_q,
                meta_type=node_props["meta_type"],
                payload=related.get("payload", {}),
            )
        
        raise ValueError(f"Unknown event kind: {kind}")
    
    @staticmethod
    def to_canonical(event: AnyEvent) -> dict:
        """Canonical representation for hashing."""
        base = {
            "kind": event.kind,
            "offset_q": RationalTimeAdapter.to_canonical(event.offset_q),
            "dur_q": RationalTimeAdapter.to_canonical(event.dur_q),
        }
        
        if isinstance(event, NoteEvent):
            base["pitch"] = PitchAdapter.to_canonical(event.pitch)
            if event.velocity is not None:
                base["velocity"] = event.velocity
            if event.tie:
                base["tie"] = event.tie
            if event.articulations:
                base["articulations"] = list(event.articulations)
            if event.lyric:
                base["lyric"] = event.lyric
        
        elif isinstance(event, ChordEvent):
            base["pitches"] = [PitchAdapter.to_canonical(p) for p in event.pitches]
            if event.velocity is not None:
                base["velocity"] = event.velocity
            if event.tie:
                base["tie"] = event.tie
            if event.articulations:
                base["articulations"] = list(event.articulations)
            if event.lyric:
                base["lyric"] = event.lyric
        
        elif isinstance(event, MetaEvent):
            base["meta_type"] = event.meta_type
            if event.payload:
                base["payload"] = dict(event.payload)
        
        return base


# =============================================================================
# Measure Adapter
# =============================================================================

class MeasureAdapter:
    """Converts MeasureSpec to/from graph storage."""
    
    @staticmethod
    def to_properties(measure: MeasureSpec) -> dict:
        """Convert to graph node properties."""
        props = {}
        
        if measure.local_time_signature:
            props.update(TimeSignatureAdapter.to_properties(
                measure.local_time_signature,
                "local_ts_"
            ))
        
        return props
    
    @staticmethod
    def to_canonical(measure: MeasureSpec) -> dict:
        """Canonical representation for hashing."""
        result = {}
        
        if measure.local_time_signature:
            result["local_ts"] = TimeSignatureAdapter.to_canonical(
                measure.local_time_signature
            )
        
        result["events"] = [EventAdapter.to_canonical(e) for e in measure.events]
        
        return result
    
    @staticmethod
    def compute_hash(measure: MeasureSpec) -> str:
        """Content hash for MeasureVersion."""
        return content_hash(MeasureAdapter.to_canonical(measure))


# =============================================================================
# Section Adapter
# =============================================================================

class SectionAdapter:
    """Converts SectionSpec to/from graph storage."""
    
    @staticmethod
    def to_properties(section: SectionSpec) -> dict:
        """Convert to graph node properties."""
        return {
            "name": section.name,
        }
    
    @staticmethod
    def to_canonical(section: SectionSpec) -> dict:
        """Canonical representation for hashing."""
        return {
            "name": section.name,
            "measures": [MeasureAdapter.to_canonical(m) for m in section.measures],
        }
    
    @staticmethod
    def compute_hash(section: SectionSpec) -> str:
        """Content hash for SectionVersion."""
        return content_hash(SectionAdapter.to_canonical(section))


# =============================================================================
# MeterMap Adapter
# =============================================================================

class MeterMapAdapter:
    """Converts MeterMap to/from graph storage."""
    
    @staticmethod
    def to_canonical(meter_map) -> dict:
        """Canonical representation for hashing."""
        return {
            "changes": [
                {
                    "at_bar": ch.at_bar,
                    "ts": TimeSignatureAdapter.to_canonical(ch.ts),
                }
                for ch in meter_map.changes
            ]
        }
    
    @staticmethod
    def compute_hash(meter_map) -> str:
        """Content hash for MeterMapVersion."""
        return content_hash(MeterMapAdapter.to_canonical(meter_map))


# =============================================================================
# TempoMap Adapter
# =============================================================================

class TempoMapAdapter:
    """Converts TempoMap to/from graph storage."""
    
    @staticmethod
    def to_canonical(tempo_map) -> dict:
        """Canonical representation for hashing."""
        return {
            "changes": [
                {
                    "at_bar": ch.at_bar,
                    "at_beat": ch.at_beat,
                    "bpm": RationalTimeAdapter.to_canonical(ch.tempo.bpm),
                    "beat_unit_den": ch.tempo.beat_unit_den,
                }
                for ch in tempo_map.changes
            ]
        }
    
    @staticmethod
    def compute_hash(tempo_map) -> str:
        """Content hash for TempoMapVersion."""
        return content_hash(TempoMapAdapter.to_canonical(tempo_map))


# =============================================================================
# Track Adapter
# =============================================================================

class TrackAdapter:
    """Converts TrackSpec to/from graph storage."""
    
    @staticmethod
    def to_properties(track: TrackSpec) -> dict:
        """Convert to graph node properties."""
        props = {
            "track_id": track.track_id,
            "name": track.config.name,
            "transposition_semitones": track.config.transposition_semitones,
        }
        
        if track.config.instrument_hint:
            props["instrument_hint"] = track.config.instrument_hint
        if track.config.midi_channel:
            props["midi_channel"] = track.config.midi_channel
        if track.config.clef:
            props["clef"] = track.config.clef
        
        return props
    
    @staticmethod
    def to_canonical(track: TrackSpec) -> dict:
        """Canonical representation for hashing."""
        return {
            "track_id": track.track_id,
            "config": {
                "name": track.config.name,
                "instrument_hint": track.config.instrument_hint,
                "midi_channel": track.config.midi_channel,
                "clef": track.config.clef,
                "transposition_semitones": track.config.transposition_semitones,
            },
            "placements": [
                {
                    "section_version_id": p.section_version_id,
                    "start_bar": p.start_bar,
                    "repeats": p.repeats,
                    "transpose_semitones": p.transpose_semitones,
                    "role": p.role,
                    "gain_db": p.gain_db,
                }
                for p in track.placements
            ],
        }
    
    @staticmethod
    def compute_hash(track: TrackSpec) -> str:
        """Content hash for TrackVersion."""
        return content_hash(TrackAdapter.to_canonical(track))


# =============================================================================
# Composition Adapter
# =============================================================================

class CompositionAdapter:
    """Converts CompositionSpec to/from graph storage."""
    
    @staticmethod
    def to_properties(composition: CompositionSpec) -> dict:
        """Convert to graph node properties."""
        return {
            "title": composition.title,
        }
    
    @staticmethod
    def to_canonical(composition: CompositionSpec) -> dict:
        """Canonical representation for hashing."""
        return {
            "title": composition.title,
            "meter_map": MeterMapAdapter.to_canonical(composition.meter_map),
            "tempo_map": TempoMapAdapter.to_canonical(composition.tempo_map),
            "tracks": [TrackAdapter.to_canonical(t) for t in composition.tracks],
        }
    
    @staticmethod
    def compute_hash(composition: CompositionSpec) -> str:
        """Content hash for CompositionVersion."""
        return content_hash(CompositionAdapter.to_canonical(composition))
