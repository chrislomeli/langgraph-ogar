"""
Unit tests for persistence adapter.

These tests verify:
- Domain → graph property conversion
- Content hashing determinism
- Canonical representation

No database required - tests the adapter logic in isolation.
"""

import pytest

from symbolic_music.domain import (
    ChordEvent,
    MeasureSpec,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    TimeSignature,
)
from symbolic_music.persistence.adapter import (
    content_hash,
    EventAdapter,
    MeasureAdapter,
    PitchAdapter,
    RationalTimeAdapter,
    TimeSignatureAdapter,
)


# =============================================================================
# RationalTimeAdapter Tests
# =============================================================================

class TestRationalTimeAdapter:
    """Tests for RationalTime conversion."""
    
    def test_to_properties(self):
        rt = RationalTime(n=3, d=4)
        props = RationalTimeAdapter.to_properties(rt)
        
        assert props == {"n": 3, "d": 4}
    
    def test_to_properties_with_prefix(self):
        rt = RationalTime(n=1, d=8)
        props = RationalTimeAdapter.to_properties(rt, prefix="offset_")
        
        assert props == {"offset_n": 1, "offset_d": 8}
    
    def test_from_properties(self):
        props = {"n": 5, "d": 16}
        rt = RationalTimeAdapter.from_properties(props)
        
        assert rt.n == 5
        assert rt.d == 16
    
    def test_from_properties_with_prefix(self):
        props = {"dur_n": 1, "dur_d": 2}
        rt = RationalTimeAdapter.from_properties(props, prefix="dur_")
        
        assert rt.n == 1
        assert rt.d == 2
    
    def test_to_canonical(self):
        rt = RationalTime(n=3, d=4)
        canonical = RationalTimeAdapter.to_canonical(rt)
        
        assert canonical == {"n": 3, "d": 4}


# =============================================================================
# PitchAdapter Tests
# =============================================================================

class TestPitchAdapter:
    """Tests for Pitch conversion."""
    
    def test_to_properties_simple(self):
        pitch = Pitch(midi=60)
        props = PitchAdapter.to_properties(pitch)
        
        assert props["midi"] == 60
        assert props["cents_n"] == 0
        assert props["cents_d"] == 1
    
    def test_to_properties_with_cents(self):
        pitch = Pitch(midi=60, cents=RationalTime(n=50, d=1))
        props = PitchAdapter.to_properties(pitch)
        
        assert props["midi"] == 60
        assert props["cents_n"] == 50
        assert props["cents_d"] == 1
    
    def test_to_properties_with_spelling(self):
        pitch = Pitch(midi=61, spelling_hint="C#4")
        props = PitchAdapter.to_properties(pitch)
        
        assert props["spelling_hint"] == "C#4"
    
    def test_from_properties(self):
        props = {"midi": 64, "cents_n": 0, "cents_d": 1, "spelling_hint": "E4"}
        pitch = PitchAdapter.from_properties(props)
        
        assert pitch.midi == 64
        assert pitch.spelling_hint == "E4"
    
    def test_canonical_excludes_spelling(self):
        """Spelling hint should not affect canonical representation."""
        p1 = Pitch(midi=61, spelling_hint="C#4")
        p2 = Pitch(midi=61, spelling_hint="Db4")
        
        assert PitchAdapter.to_canonical(p1) == PitchAdapter.to_canonical(p2)
    
    def test_hash_excludes_spelling(self):
        """Same pitch with different spelling should have same hash."""
        p1 = Pitch(midi=61, spelling_hint="C#4")
        p2 = Pitch(midi=61, spelling_hint="Db4")
        
        assert PitchAdapter.compute_hash(p1) == PitchAdapter.compute_hash(p2)
    
    def test_hash_differs_for_different_pitches(self):
        p1 = Pitch(midi=60)
        p2 = Pitch(midi=61)
        
        assert PitchAdapter.compute_hash(p1) != PitchAdapter.compute_hash(p2)


# =============================================================================
# TimeSignatureAdapter Tests
# =============================================================================

class TestTimeSignatureAdapter:
    """Tests for TimeSignature conversion."""
    
    def test_to_properties(self):
        ts = TimeSignature(num=6, den=8)
        props = TimeSignatureAdapter.to_properties(ts)
        
        assert props == {"num": 6, "den": 8}
    
    def test_to_properties_with_prefix(self):
        ts = TimeSignature(num=3, den=4)
        props = TimeSignatureAdapter.to_properties(ts, prefix="local_ts_")
        
        assert props == {"local_ts_num": 3, "local_ts_den": 4}
    
    def test_from_properties(self):
        props = {"num": 4, "den": 4}
        ts = TimeSignatureAdapter.from_properties(props)
        
        assert ts.num == 4
        assert ts.den == 4


# =============================================================================
# EventAdapter Tests
# =============================================================================

class TestEventAdapter:
    """Tests for Event conversion."""
    
    def test_note_to_properties(self):
        note = NoteEvent(
            offset_q=RationalTime(n=1, d=4),
            dur_q=RationalTime(n=1, d=4),
            pitch=Pitch(midi=60),
            velocity=100,
        )
        props = EventAdapter.to_properties(note)
        
        assert props["kind"] == "note"
        assert props["offset_n"] == 1
        assert props["offset_d"] == 4
        assert props["dur_n"] == 1
        assert props["dur_d"] == 4
        assert props["midi"] == 60
        assert props["velocity"] == 100
    
    def test_rest_to_properties(self):
        rest = RestEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=2),
        )
        props = EventAdapter.to_properties(rest)
        
        assert props["kind"] == "rest"
        assert props["dur_n"] == 1
        assert props["dur_d"] == 2
    
    def test_chord_to_properties(self):
        chord = ChordEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitches=(Pitch(midi=60), Pitch(midi=64), Pitch(midi=67)),
        )
        props = EventAdapter.to_properties(chord)
        
        assert props["kind"] == "chord"
        assert props["midi_min"] == 60
        assert props["midi_max"] == 67
    
    def test_note_to_relationships(self):
        note = NoteEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitch=Pitch(midi=60),
            articulations=("staccato", "accent"),
        )
        rels = EventAdapter.to_relationships(note)
        
        # Should have pitch and articulation relationships
        rel_types = [r[0] for r in rels]
        assert "HAS_PITCH" in rel_types
        assert "HAS_ARTICULATION" in rel_types
    
    def test_chord_to_relationships(self):
        chord = ChordEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitches=(Pitch(midi=60), Pitch(midi=64)),
        )
        rels = EventAdapter.to_relationships(chord)
        
        # Should have multiple pitch relationships
        pitch_rels = [r for r in rels if r[0] == "HAS_PITCH"]
        assert len(pitch_rels) == 2


# =============================================================================
# Content Hash Tests
# =============================================================================

class TestContentHash:
    """Tests for content-addressed hashing."""
    
    def test_hash_is_deterministic(self):
        """Same input should always produce same hash."""
        note = NoteEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitch=Pitch(midi=60),
        )
        
        hash1 = content_hash(EventAdapter.to_canonical(note))
        hash2 = content_hash(EventAdapter.to_canonical(note))
        
        assert hash1 == hash2
    
    def test_hash_differs_for_different_content(self):
        note1 = NoteEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitch=Pitch(midi=60),
        )
        note2 = NoteEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitch=Pitch(midi=61),  # Different pitch
        )
        
        hash1 = content_hash(EventAdapter.to_canonical(note1))
        hash2 = content_hash(EventAdapter.to_canonical(note2))
        
        assert hash1 != hash2
    
    def test_measure_hash_deterministic(self):
        """Measure hash should be deterministic."""
        ts = TimeSignature(num=4, den=4)
        note = NoteEvent(
            offset_q=RationalTime(n=0, d=1),
            dur_q=RationalTime(n=1, d=4),
            pitch=Pitch(midi=60),
        )
        measure = MeasureSpec(local_time_signature=ts, events=(note,))
        
        hash1 = MeasureAdapter.compute_hash(measure)
        hash2 = MeasureAdapter.compute_hash(measure)
        
        assert hash1 == hash2
    
    def test_equivalent_measures_same_hash(self):
        """Measures with same content should have same hash."""
        ts = TimeSignature(num=4, den=4)
        
        # Create two identical measures separately
        m1 = MeasureSpec(
            local_time_signature=ts,
            events=(
                NoteEvent(
                    offset_q=RationalTime(n=0, d=1),
                    dur_q=RationalTime(n=1, d=4),
                    pitch=Pitch(midi=60),
                ),
            ),
        )
        m2 = MeasureSpec(
            local_time_signature=ts,
            events=(
                NoteEvent(
                    offset_q=RationalTime(n=0, d=1),
                    dur_q=RationalTime(n=1, d=4),
                    pitch=Pitch(midi=60),
                ),
            ),
        )
        
        assert MeasureAdapter.compute_hash(m1) == MeasureAdapter.compute_hash(m2)
