#!/usr/bin/env python3
"""
Demo: Create "Twinkle Twinkle Little Star" (single part) in the graph database.

Run after setting up the schema.
"""

import sys
sys.path.insert(0, "../../src")

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
from symbolic_music.persistence import GraphMusicWriter


def rt(n: int, d: int = 1) -> RationalTime:
    """Shorthand for RationalTime."""
    return RationalTime(n=n, d=d)


def p(midi: int, spelling: str = None) -> Pitch:
    """Shorthand for Pitch."""
    return Pitch(midi=midi, spelling_hint=spelling)


# MIDI notes
C4, D4, E4, F4, G4, A4 = 60, 62, 64, 65, 67, 69


def create_twinkle_star():
    """Create Twinkle Twinkle Little Star in C major."""
    store = GraphMusicWriter()
    
    print("Creating 'Twinkle Twinkle Little Star'...")
    
    ts = TimeSignature(num=4, den=4)
    Q = rt(1, 4)  # quarter
    H = rt(1, 2)  # half
    
    # Section A
    section_a_sid = store.create_section("Verse A")
    
    m1 = MeasureSpec(
        local_time_signature=ts,
        events=(
            NoteEvent(offset_q=rt(0), dur_q=Q, pitch=p(C4, "C4")),
            NoteEvent(offset_q=rt(1, 4), dur_q=Q, pitch=p(C4, "C4")),
            NoteEvent(offset_q=rt(2, 4), dur_q=Q, pitch=p(G4, "G4")),
            NoteEvent(offset_q=rt(3, 4), dur_q=Q, pitch=p(G4, "G4")),
        ),
    )
    
    m2 = MeasureSpec(
        local_time_signature=ts,
        events=(
            NoteEvent(offset_q=rt(0), dur_q=Q, pitch=p(A4, "A4")),
            NoteEvent(offset_q=rt(1, 4), dur_q=Q, pitch=p(A4, "A4")),
            NoteEvent(offset_q=rt(2, 4), dur_q=H, pitch=p(G4, "G4")),
        ),
    )
    
    m3 = MeasureSpec(
        local_time_signature=ts,
        events=(
            NoteEvent(offset_q=rt(0), dur_q=Q, pitch=p(F4, "F4")),
            NoteEvent(offset_q=rt(1, 4), dur_q=Q, pitch=p(F4, "F4")),
            NoteEvent(offset_q=rt(2, 4), dur_q=Q, pitch=p(E4, "E4")),
            NoteEvent(offset_q=rt(3, 4), dur_q=Q, pitch=p(E4, "E4")),
        ),
    )
    
    m4 = MeasureSpec(
        local_time_signature=ts,
        events=(
            NoteEvent(offset_q=rt(0), dur_q=Q, pitch=p(D4, "D4")),
            NoteEvent(offset_q=rt(1, 4), dur_q=Q, pitch=p(D4, "D4")),
            NoteEvent(offset_q=rt(2, 4), dur_q=H, pitch=p(C4, "C4")),
        ),
    )
    
    section_a = SectionSpec(name="Verse A", measures=(m1, m2, m3, m4))
    svid_a = store.commit_section_version(section_a_sid, section_a)
    print(f"  Created Section A: {svid_a[:8]}...")
    
    # Section B
    section_b_sid = store.create_section("Verse B")
    
    m5 = MeasureSpec(
        local_time_signature=ts,
        events=(
            NoteEvent(offset_q=rt(0), dur_q=Q, pitch=p(G4, "G4")),
            NoteEvent(offset_q=rt(1, 4), dur_q=Q, pitch=p(G4, "G4")),
            NoteEvent(offset_q=rt(2, 4), dur_q=Q, pitch=p(F4, "F4")),
            NoteEvent(offset_q=rt(3, 4), dur_q=Q, pitch=p(F4, "F4")),
        ),
    )
    
    m6 = MeasureSpec(
        local_time_signature=ts,
        events=(
            NoteEvent(offset_q=rt(0), dur_q=Q, pitch=p(E4, "E4")),
            NoteEvent(offset_q=rt(1, 4), dur_q=Q, pitch=p(E4, "E4")),
            NoteEvent(offset_q=rt(2, 4), dur_q=H, pitch=p(D4, "D4")),
        ),
    )
    
    section_b = SectionSpec(name="Verse B", measures=(m5, m6, m5, m6))
    svid_b = store.commit_section_version(section_b_sid, section_b)
    print(f"  Created Section B: {svid_b[:8]}...")
    
    # Composition
    comp_cid = store.create_composition("Twinkle Twinkle Little Star")
    
    meter_map = MeterMap(changes=(MeterChange(at_bar=1, ts=ts),))
    tempo_map = TempoMap(changes=(
        TempoChange(at_bar=1, at_beat=1, tempo=TempoValue(bpm=rt(100), beat_unit_den=4)),
    ))
    
    melody_track = TrackSpec(
        track_id="melody-track",
        config=TrackConfig(
            name="Melody",
            instrument_hint="piano",
            midi_channel=1,
            clef="treble",
        ),
        placements=(
            SectionPlacement(section_version_id=svid_a, start_bar=1, repeats=1),
            SectionPlacement(section_version_id=svid_b, start_bar=5, repeats=1),
            SectionPlacement(section_version_id=svid_a, start_bar=9, repeats=1),
        ),
    )
    
    composition = CompositionSpec(
        title="Twinkle Twinkle Little Star",
        meter_map=meter_map,
        tempo_map=tempo_map,
        tracks=(melody_track,),
    )
    
    cvid = store.commit_composition_version(comp_cid, composition)
    
    print(f"\nCreated composition:")
    print(f"  Composition ID: {comp_cid[:8]}...")
    print(f"  Version ID: {cvid[:8]}...")
    print(f"  Structure: A-B-A")
    
    return comp_cid


if __name__ == "__main__":
    create_twinkle_star()
    print("\nExplore in Memgraph Lab (http://localhost:7444)")
