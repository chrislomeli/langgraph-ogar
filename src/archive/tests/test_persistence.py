"""
Integration tests for persistence layer.

These tests verify:
- Writing compositions to Memgraph
- Reading compositions back
- Roundtrip integrity (write → read → compare)

Requires: docker-compose up -d (Memgraph running)
"""

import pytest

from symbolic_music.domain import (
    CompositionSpec,
    MeasureSpec,
    MeterChange,
    MeterMap,
    NoteEvent,
    Pitch,
    RationalTime,
    SectionPlacement,
    SectionSpec,
    TempoChange,
    TempoMap,
    TempoValue,
    TimeSignature,
    TrackConfig,
    TrackSpec,
)


# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Helper Functions
# =============================================================================

def rt(n: int, d: int = 1) -> RationalTime:
    """Shorthand for RationalTime."""
    return RationalTime(n=n, d=d)


def make_simple_section(name: str, num_measures: int = 2) -> SectionSpec:
    """Create a simple section with quarter notes."""
    ts = TimeSignature(num=4, den=4)
    measures = []
    
    for i in range(num_measures):
        notes = tuple(
            NoteEvent(
                offset_q=rt(j, 4),
                dur_q=rt(1, 4),
                pitch=Pitch(midi=60 + j),
            )
            for j in range(4)
        )
        measures.append(MeasureSpec(local_time_signature=ts, events=notes))
    
    return SectionSpec(name=name, measures=tuple(measures))


def make_simple_composition(title: str, section: SectionSpec, svid: str) -> CompositionSpec:
    """Create a simple composition with one track."""
    return CompositionSpec(
        title=title,
        meter_map=MeterMap(changes=(
            MeterChange(at_bar=1, ts=TimeSignature(num=4, den=4)),
        )),
        tempo_map=TempoMap(changes=(
            TempoChange(at_bar=1, at_beat=1, tempo=TempoValue(bpm=rt(120), beat_unit_den=4)),
        )),
        tracks=(
            TrackSpec(
                track_id="test-track",
                config=TrackConfig(name="Test Track", instrument_hint="piano"),
                placements=(
                    SectionPlacement(section_version_id=svid, start_bar=1),
                ),
            ),
        ),
    )


# =============================================================================
# Section Tests
# =============================================================================

class TestSectionPersistence:
    """Tests for section write/read."""
    
    def test_create_section_identity(self, clean_db):
        """Creating a section returns a stable ID."""
        sid = clean_db.create_section("Test Section")
        assert sid is not None
        assert len(sid) > 0
    
    def test_commit_section_version(self, clean_db):
        """Committing a section version returns version ID."""
        sid = clean_db.create_section("Verse")
        section = make_simple_section("Verse")
        
        svid = clean_db.commit_section_version(sid, section)
        
        assert svid is not None
        assert len(svid) > 0
    
    def test_section_content_addressing(self, clean_db):
        """Same content should return same version (content-addressed)."""
        sid = clean_db.create_section("Verse")
        section = make_simple_section("Verse", num_measures=1)
        
        svid1 = clean_db.commit_section_version(sid, section)
        svid2 = clean_db.commit_section_version(sid, section)
        
        # Same content = same version ID
        assert svid1 == svid2


# =============================================================================
# Composition Tests
# =============================================================================

class TestCompositionPersistence:
    """Tests for composition write/read."""
    
    def test_create_composition_identity(self, clean_db):
        """Creating a composition returns a stable ID."""
        cid = clean_db.create_composition("Test Song")
        assert cid is not None
        assert len(cid) > 0
    
    def test_commit_composition_version(self, clean_db):
        """Committing a composition version returns version ID."""
        # Create section first
        sid = clean_db.create_section("Intro")
        section = make_simple_section("Intro")
        svid = clean_db.commit_section_version(sid, section)
        
        # Create composition
        cid = clean_db.create_composition("My Song")
        composition = make_simple_composition("My Song", section, svid)
        
        cvid = clean_db.commit_composition_version(cid, composition)
        
        assert cvid is not None
        assert len(cvid) > 0


# =============================================================================
# Roundtrip Tests
# =============================================================================

class TestRoundtrip:
    """Tests for write → read integrity."""
    
    def test_composition_roundtrip(self, clean_db, db_reader):
        """Write a composition and read it back."""
        # Create section
        sid = clean_db.create_section("Chorus")
        section = make_simple_section("Chorus", num_measures=2)
        svid = clean_db.commit_section_version(sid, section)
        
        # Create composition
        cid = clean_db.create_composition("Roundtrip Test")
        original = make_simple_composition("Roundtrip Test", section, svid)
        clean_db.commit_composition_version(cid, original)
        
        # Read back
        loaded, sections = db_reader.load_composition_by_title("Roundtrip Test")
        
        # Verify
        assert loaded.title == original.title
        assert len(loaded.tracks) == len(original.tracks)
        assert loaded.tracks[0].track_id == original.tracks[0].track_id
        assert loaded.tracks[0].config.name == original.tracks[0].config.name
    
    def test_meter_map_roundtrip(self, clean_db, db_reader):
        """Meter map should survive roundtrip."""
        # Create with meter change
        sid = clean_db.create_section("Test")
        section = make_simple_section("Test")
        svid = clean_db.commit_section_version(sid, section)
        
        cid = clean_db.create_composition("Meter Test")
        composition = CompositionSpec(
            title="Meter Test",
            meter_map=MeterMap(changes=(
                MeterChange(at_bar=1, ts=TimeSignature(num=4, den=4)),
                MeterChange(at_bar=5, ts=TimeSignature(num=3, den=4)),
            )),
            tempo_map=TempoMap(changes=(
                TempoChange(at_bar=1, at_beat=1, tempo=TempoValue(bpm=rt(120), beat_unit_den=4)),
            )),
            tracks=(
                TrackSpec(
                    track_id="track",
                    config=TrackConfig(name="Track"),
                    placements=(SectionPlacement(section_version_id=svid, start_bar=1),),
                ),
            ),
        )
        clean_db.commit_composition_version(cid, composition)
        
        # Read back
        loaded, _ = db_reader.load_composition_by_title("Meter Test")
        
        assert len(loaded.meter_map.changes) == 2
        assert loaded.meter_map.changes[0].ts.num == 4
        assert loaded.meter_map.changes[1].ts.num == 3
        assert loaded.meter_map.changes[1].at_bar == 5
    
    def test_note_events_roundtrip(self, clean_db, db_reader):
        """Note events should survive roundtrip with all properties."""
        # Create section with specific notes
        ts = TimeSignature(num=4, den=4)
        note = NoteEvent(
            offset_q=rt(0),
            dur_q=rt(1, 4),
            pitch=Pitch(midi=64, spelling_hint="E4"),
            velocity=80,
        )
        measure = MeasureSpec(local_time_signature=ts, events=(note,))
        section = SectionSpec(name="Note Test", measures=(measure,))
        
        sid = clean_db.create_section("Note Test")
        svid = clean_db.commit_section_version(sid, section)
        
        cid = clean_db.create_composition("Note Event Test")
        composition = make_simple_composition("Note Event Test", section, svid)
        clean_db.commit_composition_version(cid, composition)
        
        # Read back
        _, sections = db_reader.load_composition_by_title("Note Event Test")
        loaded_section = sections[svid]
        loaded_note = loaded_section.measures[0].events[0]
        
        assert loaded_note.pitch.midi == 64
        assert loaded_note.velocity == 80
        assert loaded_note.dur_q == rt(1, 4)
    
    def test_multitrack_roundtrip(self, clean_db, db_reader):
        """Multiple tracks should survive roundtrip."""
        # Create sections
        sid1 = clean_db.create_section("Melody")
        section1 = make_simple_section("Melody")
        svid1 = clean_db.commit_section_version(sid1, section1)
        
        sid2 = clean_db.create_section("Bass")
        section2 = make_simple_section("Bass")
        svid2 = clean_db.commit_section_version(sid2, section2)
        
        # Create composition with two tracks
        cid = clean_db.create_composition("Multitrack Test")
        composition = CompositionSpec(
            title="Multitrack Test",
            meter_map=MeterMap(changes=(
                MeterChange(at_bar=1, ts=TimeSignature(num=4, den=4)),
            )),
            tempo_map=TempoMap(changes=(
                TempoChange(at_bar=1, at_beat=1, tempo=TempoValue(bpm=rt(100), beat_unit_den=4)),
            )),
            tracks=(
                TrackSpec(
                    track_id="melody-track",
                    config=TrackConfig(name="Melody", instrument_hint="piano", clef="treble"),
                    placements=(SectionPlacement(section_version_id=svid1, start_bar=1),),
                ),
                TrackSpec(
                    track_id="bass-track",
                    config=TrackConfig(name="Bass", instrument_hint="bass", clef="bass"),
                    placements=(SectionPlacement(section_version_id=svid2, start_bar=1, transpose_semitones=-12),),
                ),
            ),
        )
        clean_db.commit_composition_version(cid, composition)
        
        # Read back
        loaded, sections = db_reader.load_composition_by_title("Multitrack Test")
        
        assert len(loaded.tracks) == 2
        
        # Tracks are sorted by ID
        assert loaded.tracks[0].track_id == "bass-track"
        assert loaded.tracks[1].track_id == "melody-track"
        
        # Check track configs
        bass_track = loaded.get_track("bass-track")
        assert bass_track.config.clef == "bass"
        
        melody_track = loaded.get_track("melody-track")
        assert melody_track.config.instrument_hint == "piano"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestPersistenceErrors:
    """Tests for error conditions."""
    
    def test_load_nonexistent_composition(self, clean_db, db_reader):
        """Loading non-existent composition should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            db_reader.load_composition_by_title("Does Not Exist")
