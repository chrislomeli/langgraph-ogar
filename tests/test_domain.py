"""
Unit tests for domain models.

These tests verify:
- Value object behavior (immutability, equality)
- Validation rules (invariants)
- Domain operations (arithmetic, transposition)

No external dependencies - pure logic tests.
"""

import pytest
from fractions import Fraction

from symbolic_music.domain import (
    ChordEvent,
    CompositionSpec,
    DomainError,
    InvalidPitchError,
    InvalidTimeSignatureError,
    MeasureSpec,
    MeterChange,
    MeterMap,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    RT_ZERO,
    RT_QUARTER,
    RT_HALF,
    SectionSpec,
    TimeBoundsError,
    TimeSignature,
    TrackConfig,
    TrackSpec,
)


# =============================================================================
# RationalTime Tests
# =============================================================================

class TestRationalTime:
    """Tests for exact rational time representation."""
    
    def test_creation(self):
        rt = RationalTime(n=1, d=4)
        assert rt.n == 1
        assert rt.d == 4
    
    def test_auto_reduces(self):
        """Fractions should auto-reduce to lowest terms."""
        rt = RationalTime(n=2, d=4)
        assert rt.n == 1
        assert rt.d == 2
    
    def test_negative_denominator_normalized(self):
        """Negative sign should move to numerator."""
        rt = RationalTime(n=1, d=-4)
        assert rt.n == -1
        assert rt.d == 4
    
    def test_zero_denominator_raises(self):
        with pytest.raises(Exception, match="cannot be 0"):
            RationalTime(n=1, d=0)
    
    def test_addition(self, quarter_note, half_note):
        result = quarter_note + quarter_note
        assert result == half_note
    
    def test_subtraction(self, half_note, quarter_note):
        result = half_note - quarter_note
        assert result == quarter_note
    
    def test_multiplication_by_int(self, quarter_note, half_note):
        result = quarter_note * 2
        assert result == half_note
    
    def test_division_by_int(self, half_note, quarter_note):
        result = half_note / 2
        assert result == quarter_note
    
    def test_comparison(self):
        small = RationalTime(n=1, d=8)
        large = RationalTime(n=1, d=4)
        assert small < large
        assert large > small
        assert small <= large
        assert large >= small
    
    def test_equality(self):
        a = RationalTime(n=1, d=4)
        b = RationalTime(n=2, d=8)  # Same value, different representation
        assert a == b
    
    def test_as_float(self, quarter_note):
        assert quarter_note.as_float() == 0.25
    
    def test_as_fraction(self, quarter_note):
        assert quarter_note.as_fraction() == Fraction(1, 4)
    
    def test_from_fraction(self):
        rt = RationalTime.from_fraction(Fraction(3, 8))
        assert rt.n == 3
        assert rt.d == 8
    
    def test_parse_fraction_string(self):
        rt = RationalTime.parse("3/4")
        assert rt.n == 3
        assert rt.d == 4
    
    def test_parse_integer_string(self):
        rt = RationalTime.parse("7")
        assert rt.n == 7
        assert rt.d == 1
    
    def test_str_representation(self):
        assert str(RationalTime(n=3, d=4)) == "3/4"
        assert str(RationalTime(n=2, d=1)) == "2"


# =============================================================================
# Pitch Tests
# =============================================================================

class TestPitch:
    """Tests for pitch representation."""
    
    def test_creation(self):
        p = Pitch(midi=60)
        assert p.midi == 60
    
    def test_midi_range_validation(self):
        Pitch(midi=0)    # Valid minimum
        Pitch(midi=127)  # Valid maximum
        
        with pytest.raises(Exception):  # Pydantic validation
            Pitch(midi=-1)
        with pytest.raises(Exception):
            Pitch(midi=128)
    
    def test_equality_ignores_spelling(self):
        """Two pitches with same MIDI are equal regardless of spelling."""
        c_sharp = Pitch(midi=61, spelling_hint="C#4")
        d_flat = Pitch(midi=61, spelling_hint="Db4")
        assert c_sharp == d_flat
    
    def test_hash_ignores_spelling(self):
        """Hash should be same for equal pitches."""
        c_sharp = Pitch(midi=61, spelling_hint="C#4")
        d_flat = Pitch(midi=61, spelling_hint="Db4")
        assert hash(c_sharp) == hash(d_flat)
    
    def test_transpose_up(self):
        p = Pitch(midi=60)
        transposed = p.transpose(12)
        assert transposed.midi == 72
    
    def test_transpose_down(self):
        p = Pitch(midi=72)
        transposed = p.transpose(-12)
        assert transposed.midi == 60
    
    def test_transpose_out_of_range_raises(self):
        p = Pitch(midi=120)
        with pytest.raises(InvalidPitchError):
            p.transpose(10)  # Would be 130, out of range
    
    def test_microtonal_cents(self):
        """Pitch with microtonal offset."""
        p = Pitch(midi=60, cents=RationalTime(n=50, d=1))
        assert p.cents.n == 50
    
    def test_frequency_a4(self):
        """A4 should be 440 Hz."""
        a4 = Pitch(midi=69)
        assert abs(a4.frequency_hz() - 440.0) < 0.01
    
    def test_frequency_a5(self):
        """A5 should be 880 Hz (octave above A4)."""
        a5 = Pitch(midi=81)
        assert abs(a5.frequency_hz() - 880.0) < 0.01
    
    def test_ordering(self):
        """Pitches should be orderable by MIDI number."""
        low = Pitch(midi=48)
        mid = Pitch(midi=60)
        high = Pitch(midi=72)
        assert low < mid < high


# =============================================================================
# TimeSignature Tests
# =============================================================================

class TestTimeSignature:
    """Tests for time signature."""
    
    def test_creation(self, time_sig_4_4):
        assert time_sig_4_4.num == 4
        assert time_sig_4_4.den == 4
    
    def test_denominator_must_be_power_of_2(self):
        TimeSignature(num=4, den=4)   # Valid
        TimeSignature(num=6, den=8)   # Valid
        TimeSignature(num=2, den=2)   # Valid
        TimeSignature(num=5, den=16)  # Valid
        
        with pytest.raises(Exception, match="power of 2"):
            TimeSignature(num=4, den=3)  # 3 is not power of 2
        
        with pytest.raises(Exception, match="power of 2"):
            TimeSignature(num=4, den=5)  # 5 is not power of 2
    
    def test_measure_length_4_4(self, time_sig_4_4):
        """4/4 measure = 1 whole note = 4 quarter notes."""
        length = time_sig_4_4.measure_length_quarters()
        assert length == RationalTime(n=4, d=1)
    
    def test_measure_length_3_4(self, time_sig_3_4):
        """3/4 measure = 3 quarter notes."""
        length = time_sig_3_4.measure_length_quarters()
        assert length == RationalTime(n=3, d=1)
    
    def test_measure_length_6_8(self):
        """6/8 measure = 3 quarter notes."""
        ts = TimeSignature(num=6, den=8)
        length = ts.measure_length_quarters()
        assert length == RationalTime(n=3, d=1)
    
    def test_str_representation(self, time_sig_4_4):
        assert str(time_sig_4_4) == "4/4"


# =============================================================================
# Event Tests
# =============================================================================

class TestNoteEvent:
    """Tests for note events."""
    
    def test_creation(self, quarter_note):
        note = NoteEvent(
            offset_q=RT_ZERO,
            dur_q=quarter_note,
            pitch=Pitch(midi=60),
        )
        assert note.kind == "note"
        assert note.pitch.midi == 60
    
    def test_duration_must_be_positive(self):
        with pytest.raises(Exception, match="Duration must be"):
            NoteEvent(
                offset_q=RT_ZERO,
                dur_q=RT_ZERO,  # Zero duration
                pitch=Pitch(midi=60),
            )
    
    def test_offset_must_be_non_negative(self, quarter_note):
        with pytest.raises(Exception, match="Offset must be"):
            NoteEvent(
                offset_q=RationalTime(n=-1, d=4),  # Negative offset
                dur_q=quarter_note,
                pitch=Pitch(midi=60),
            )
    
    def test_end_calculation(self, quarter_note):
        note = NoteEvent(
            offset_q=quarter_note,
            dur_q=quarter_note,
            pitch=Pitch(midi=60),
        )
        assert note.end_q() == RationalTime(n=1, d=2)
    
    def test_transpose(self, quarter_note):
        note = NoteEvent(
            offset_q=RT_ZERO,
            dur_q=quarter_note,
            pitch=Pitch(midi=60),
        )
        transposed = note.transpose(12)
        assert transposed.pitch.midi == 72
        assert transposed.offset_q == note.offset_q  # Timing preserved
        assert transposed.dur_q == note.dur_q


class TestRestEvent:
    """Tests for rest events."""
    
    def test_creation(self, quarter_note):
        rest = RestEvent(offset_q=RT_ZERO, dur_q=quarter_note)
        assert rest.kind == "rest"
    
    def test_duration_must_be_positive(self):
        with pytest.raises(Exception, match="Duration must be"):
            RestEvent(offset_q=RT_ZERO, dur_q=RT_ZERO)


class TestChordEvent:
    """Tests for chord events."""
    
    def test_creation(self, quarter_note):
        chord = ChordEvent(
            offset_q=RT_ZERO,
            dur_q=quarter_note,
            pitches=(Pitch(midi=60), Pitch(midi=64), Pitch(midi=67)),
        )
        assert chord.kind == "chord"
        assert len(chord.pitches) == 3
    
    def test_minimum_two_pitches(self, quarter_note):
        with pytest.raises(Exception):  # Pydantic validation
            ChordEvent(
                offset_q=RT_ZERO,
                dur_q=quarter_note,
                pitches=(Pitch(midi=60),),  # Only one pitch
            )
    
    def test_pitches_sorted(self, quarter_note):
        """Chord pitches should be auto-sorted low to high."""
        chord = ChordEvent(
            offset_q=RT_ZERO,
            dur_q=quarter_note,
            pitches=(Pitch(midi=67), Pitch(midi=60), Pitch(midi=64)),
        )
        assert chord.pitches[0].midi == 60
        assert chord.pitches[1].midi == 64
        assert chord.pitches[2].midi == 67
    
    def test_pitches_must_be_unique(self, quarter_note):
        with pytest.raises(Exception, match="must be unique"):
            ChordEvent(
                offset_q=RT_ZERO,
                dur_q=quarter_note,
                pitches=(Pitch(midi=60), Pitch(midi=60)),  # Duplicate
            )
    
    def test_transpose(self, quarter_note):
        chord = ChordEvent(
            offset_q=RT_ZERO,
            dur_q=quarter_note,
            pitches=(Pitch(midi=60), Pitch(midi=64)),
        )
        transposed = chord.transpose(12)
        assert transposed.pitches[0].midi == 72
        assert transposed.pitches[1].midi == 76


# =============================================================================
# MeasureSpec Tests
# =============================================================================

class TestMeasureSpec:
    """Tests for measure specification."""
    
    def test_empty_measure(self):
        m = MeasureSpec()
        assert len(m.events) == 0
    
    def test_events_sorted_by_offset(self, quarter_note):
        """Events should be auto-sorted by offset."""
        late_note = NoteEvent(
            offset_q=RationalTime(n=1, d=2),
            dur_q=quarter_note,
            pitch=Pitch(midi=62),
        )
        early_note = NoteEvent(
            offset_q=RT_ZERO,
            dur_q=quarter_note,
            pitch=Pitch(midi=60),
        )
        
        m = MeasureSpec(events=(late_note, early_note))
        
        assert m.events[0].pitch.midi == 60  # Early note first
        assert m.events[1].pitch.midi == 62
    
    def test_event_exceeds_measure_raises(self, time_sig_4_4, quarter_note):
        """Event extending past measure boundary should raise."""
        long_note = NoteEvent(
            offset_q=RationalTime(n=3, d=1),  # Beat 4
            dur_q=RationalTime(n=2, d=1),     # 2 beats - extends past measure
            pitch=Pitch(midi=60),
        )
        
        # Pydantic wraps domain errors in ValidationError
        with pytest.raises(Exception, match="exceeds measure length"):
            MeasureSpec(
                local_time_signature=time_sig_4_4,
                events=(long_note,),
            )


# =============================================================================
# SectionSpec Tests
# =============================================================================

class TestSectionSpec:
    """Tests for section specification."""
    
    def test_creation(self, time_sig_4_4, quarter_note):
        note = NoteEvent(offset_q=RT_ZERO, dur_q=quarter_note, pitch=Pitch(midi=60))
        measure = MeasureSpec(local_time_signature=time_sig_4_4, events=(note,))
        
        section = SectionSpec(name="Verse", measures=(measure,))
        
        assert section.name == "Verse"
        assert len(section.measures) == 1
    
    def test_name_cannot_be_empty(self):
        with pytest.raises(Exception, match="cannot be empty"):
            SectionSpec(name="", measures=(MeasureSpec(),))
    
    def test_name_stripped(self):
        section = SectionSpec(name="  Chorus  ", measures=(MeasureSpec(),))
        assert section.name == "Chorus"


# =============================================================================
# MeterMap Tests
# =============================================================================

class TestMeterMap:
    """Tests for meter map."""
    
    def test_must_start_at_bar_1(self, time_sig_4_4):
        with pytest.raises(Exception, match="must start at bar 1"):
            MeterMap(changes=(
                MeterChange(at_bar=2, ts=time_sig_4_4),  # Doesn't start at 1
            ))
    
    def test_changes_must_be_increasing(self, time_sig_4_4, time_sig_3_4):
        with pytest.raises(Exception, match="strictly increasing"):
            MeterMap(changes=(
                MeterChange(at_bar=1, ts=time_sig_4_4),
                MeterChange(at_bar=5, ts=time_sig_3_4),
                MeterChange(at_bar=3, ts=time_sig_4_4),  # Out of order
            ))
    
    def test_time_signature_at(self, time_sig_4_4, time_sig_3_4):
        meter_map = MeterMap(changes=(
            MeterChange(at_bar=1, ts=time_sig_4_4),
            MeterChange(at_bar=5, ts=time_sig_3_4),
        ))
        
        assert meter_map.time_signature_at(1) == time_sig_4_4
        assert meter_map.time_signature_at(4) == time_sig_4_4
        assert meter_map.time_signature_at(5) == time_sig_3_4
        assert meter_map.time_signature_at(10) == time_sig_3_4


# =============================================================================
# CompositionSpec Tests
# =============================================================================

class TestCompositionSpec:
    """Tests for composition specification."""
    
    def test_title_cannot_be_empty(self, simple_meter_map, simple_tempo_map):
        with pytest.raises(Exception, match="cannot be empty"):
            CompositionSpec(
                title="",
                meter_map=simple_meter_map,
                tempo_map=simple_tempo_map,
            )
    
    def test_track_ids_must_be_unique(self, simple_meter_map, simple_tempo_map):
        track1 = TrackSpec(
            track_id="track-1",
            config=TrackConfig(name="Piano"),
        )
        track2 = TrackSpec(
            track_id="track-1",  # Duplicate ID
            config=TrackConfig(name="Bass"),
        )
        
        with pytest.raises(Exception, match="must be unique"):
            CompositionSpec(
                title="Test",
                meter_map=simple_meter_map,
                tempo_map=simple_tempo_map,
                tracks=(track1, track2),
            )
    
    def test_tracks_sorted_by_id(self, simple_meter_map, simple_tempo_map):
        track_b = TrackSpec(track_id="b-track", config=TrackConfig(name="B"))
        track_a = TrackSpec(track_id="a-track", config=TrackConfig(name="A"))
        
        comp = CompositionSpec(
            title="Test",
            meter_map=simple_meter_map,
            tempo_map=simple_tempo_map,
            tracks=(track_b, track_a),
        )
        
        assert comp.tracks[0].track_id == "a-track"
        assert comp.tracks[1].track_id == "b-track"
