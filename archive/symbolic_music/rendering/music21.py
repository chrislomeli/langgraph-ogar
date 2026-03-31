"""
Render domain objects to music21 Score.

Converts domain models (CompositionSpec, TrackSpec, SectionSpec, MeasureSpec, events)
into a music21 Score that can be displayed, played, or exported to MusicXML/MIDI.
"""

from typing import Optional

import music21 as m21

from symbolic_music.domain import (
    ChordEvent,
    CompositionSpec,
    MeasureSpec,
    MetaEvent,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    SectionSpec,
    TrackSpec,
)


def rt_to_quarterLength(rt: RationalTime) -> float:
    """Convert RationalTime to music21 quarterLength (quarter note = 1.0)."""
    return rt.as_float() * 4.0


def pitch_to_m21(p: Pitch, transpose_semitones: int = 0) -> m21.pitch.Pitch:
    """Convert domain Pitch to music21 Pitch."""
    midi = p.midi + transpose_semitones
    m21p = m21.pitch.Pitch(midi=midi)
    if p.spelling_hint:
        try:
            hint_pitch = m21.pitch.Pitch(p.spelling_hint)
            if transpose_semitones != 0:
                hint_pitch.midi = midi
            m21p = hint_pitch
        except Exception:
            pass
    return m21p


def render_note_event(event: NoteEvent, transpose_semitones: int = 0) -> m21.note.Note:
    """Convert NoteEvent to music21 Note."""
    m21p = pitch_to_m21(event.pitch, transpose_semitones)
    n = m21.note.Note(m21p)
    n.quarterLength = rt_to_quarterLength(event.dur_q)
    
    if event.velocity is not None:
        n.volume.velocity = event.velocity
    
    if event.tie:
        from music21 import tie
        if event.tie == "start":
            n.tie = tie.Tie("start")
        elif event.tie == "stop":
            n.tie = tie.Tie("stop")
        elif event.tie == "continue":
            n.tie = tie.Tie("continue")
    
    if event.lyric:
        n.lyric = event.lyric
    
    if event.articulations:
        from music21 import articulations
        for artic in event.articulations:
            artic_lower = artic.lower()
            if artic_lower == "staccato":
                n.articulations.append(articulations.Staccato())
            elif artic_lower == "accent":
                n.articulations.append(articulations.Accent())
            elif artic_lower == "tenuto":
                n.articulations.append(articulations.Tenuto())
            elif artic_lower == "marcato":
                n.articulations.append(articulations.StrongAccent())
            elif artic_lower == "fermata":
                n.articulations.append(articulations.Fermata())
    
    return n


def render_rest_event(event: RestEvent) -> m21.note.Rest:
    """Convert RestEvent to music21 Rest."""
    r = m21.note.Rest()
    r.quarterLength = rt_to_quarterLength(event.dur_q)
    return r


def render_chord_event(event: ChordEvent, transpose_semitones: int = 0) -> m21.chord.Chord:
    """Convert ChordEvent to music21 Chord."""
    pitches = [pitch_to_m21(p, transpose_semitones) for p in event.pitches]
    c = m21.chord.Chord(pitches)
    c.quarterLength = rt_to_quarterLength(event.dur_q)
    
    if event.velocity is not None:
        c.volume.velocity = event.velocity
    
    if event.tie:
        from music21 import tie
        if event.tie == "start":
            c.tie = tie.Tie("start")
        elif event.tie == "stop":
            c.tie = tie.Tie("stop")
        elif event.tie == "continue":
            c.tie = tie.Tie("continue")
    
    if event.lyric:
        c.lyric = event.lyric
    
    return c


def render_measure(
    measure: MeasureSpec,
    measure_number: int,
    transpose_semitones: int = 0,
    include_time_sig: bool = False,
) -> m21.stream.Measure:
    """Convert MeasureSpec to music21 Measure."""
    m = m21.stream.Measure(number=measure_number)
    
    if include_time_sig and measure.local_time_signature:
        ts = measure.local_time_signature
        m21_ts = m21.meter.TimeSignature(f"{ts.num}/{ts.den}")
        m.append(m21_ts)
    
    sorted_events = sorted(measure.events, key=lambda e: (e.offset_q.n / e.offset_q.d))
    
    for event in sorted_events:
        offset_ql = rt_to_quarterLength(event.offset_q)
        
        if isinstance(event, NoteEvent):
            elem = render_note_event(event, transpose_semitones)
        elif isinstance(event, RestEvent):
            elem = render_rest_event(event)
        elif isinstance(event, ChordEvent):
            elem = render_chord_event(event, transpose_semitones)
        elif isinstance(event, MetaEvent):
            elem = render_meta_event(event)
            if elem is None:
                continue
        else:
            continue
        
        m.insert(offset_ql, elem)
    
    return m


def render_meta_event(event: MetaEvent):
    """Convert MetaEvent to music21 element (or None if not supported)."""
    if event.meta_type == "clef":
        clef_name = event.payload.get("clef", "treble")
        if clef_name == "treble":
            return m21.clef.TrebleClef()
        elif clef_name == "bass":
            return m21.clef.BassClef()
        elif clef_name == "alto":
            return m21.clef.AltoClef()
        elif clef_name == "tenor":
            return m21.clef.TenorClef()
    elif event.meta_type == "dynamic":
        from music21 import dynamics
        dyn_val = event.payload.get("value", "mf")
        return dynamics.Dynamic(dyn_val)
    elif event.meta_type == "text":
        from music21 import expressions
        text = event.payload.get("text", "")
        return expressions.TextExpression(text)
    
    return None


def render_section(
    section: SectionSpec,
    start_measure: int,
    transpose_semitones: int = 0,
) -> list[m21.stream.Measure]:
    """Convert SectionSpec to list of music21 Measures."""
    measures = []
    for i, measure_spec in enumerate(section.measures):
        measure_num = start_measure + i
        include_ts = (i == 0)
        m = render_measure(
            measure_spec,
            measure_number=measure_num,
            transpose_semitones=transpose_semitones,
            include_time_sig=include_ts,
        )
        measures.append(m)
    return measures


def render_track(
    track: TrackSpec,
    sections_by_svid: dict[str, SectionSpec],
) -> m21.stream.Part:
    """Convert TrackSpec to music21 Part."""
    part = m21.stream.Part()
    part.id = track.track_id
    part.partName = track.config.name
    
    if track.config.instrument_hint:
        inst = _get_instrument(track.config.instrument_hint)
        if inst:
            part.insert(0, inst)
    
    if track.config.clef:
        if track.config.clef == "treble":
            part.insert(0, m21.clef.TrebleClef())
        elif track.config.clef == "bass":
            part.insert(0, m21.clef.BassClef())
        elif track.config.clef == "alto":
            part.insert(0, m21.clef.AltoClef())
        elif track.config.clef == "tenor":
            part.insert(0, m21.clef.TenorClef())
    
    for placement in track.placements:
        section = sections_by_svid.get(placement.section_version_id)
        if section is None:
            continue
        
        total_transpose = track.config.transposition_semitones + placement.transpose_semitones
        
        for repeat in range(placement.repeats):
            measures = render_section(
                section,
                start_measure=placement.start_bar,
                transpose_semitones=total_transpose,
            )
            for m in measures:
                part.append(m)
    
    return part


def _get_instrument(hint: str) -> Optional[m21.instrument.Instrument]:
    """Map instrument hint to music21 Instrument."""
    hint_lower = hint.lower().replace("_", " ").replace("-", " ")
    
    mapping = {
        "piano": m21.instrument.Piano,
        "acoustic piano": m21.instrument.Piano,
        "violin": m21.instrument.Violin,
        "viola": m21.instrument.Viola,
        "cello": m21.instrument.Violoncello,
        "bass": m21.instrument.Bass,
        "bass guitar": m21.instrument.ElectricBass,
        "electric bass": m21.instrument.ElectricBass,
        "acoustic guitar": m21.instrument.AcousticGuitar,
        "electric guitar": m21.instrument.ElectricGuitar,
        "guitar": m21.instrument.Guitar,
        "flute": m21.instrument.Flute,
        "clarinet": m21.instrument.Clarinet,
        "oboe": m21.instrument.Oboe,
        "trumpet": m21.instrument.Trumpet,
        "trombone": m21.instrument.Trombone,
        "french horn": m21.instrument.Horn,
        "horn": m21.instrument.Horn,
        "saxophone": m21.instrument.Saxophone,
        "alto sax": m21.instrument.AltoSaxophone,
        "tenor sax": m21.instrument.TenorSaxophone,
        "drums": m21.instrument.UnpitchedPercussion,
        "percussion": m21.instrument.UnpitchedPercussion,
        "voice": m21.instrument.Vocalist,
        "soprano": m21.instrument.Soprano,
        "alto": m21.instrument.Alto,
        "tenor": m21.instrument.Tenor,
        "baritone": m21.instrument.Baritone,
    }
    
    inst_class = mapping.get(hint_lower)
    if inst_class:
        return inst_class()
    return None


def render_composition(
    composition: CompositionSpec,
    sections_by_svid: dict[str, SectionSpec],
) -> m21.stream.Score:
    """Convert CompositionSpec to music21 Score."""
    score = m21.stream.Score()
    score.metadata = m21.metadata.Metadata()
    score.metadata.title = composition.title
    
    if composition.tempo_map.changes:
        first_tempo = composition.tempo_map.changes[0].tempo
        bpm = first_tempo.bpm.as_float()
        score.insert(0, m21.tempo.MetronomeMark(number=bpm))
    
    for track in composition.tracks:
        part = render_track(track, sections_by_svid)
        score.append(part)
    
    return score


def render_composition_from_graph(composition_title: str) -> m21.stream.Score:
    """Load a composition from the graph and render to music21 Score."""
    from symbolic_music.persistence import GraphMusicReader
    
    reader = GraphMusicReader()
    composition, sections = reader.load_composition_by_title(composition_title)
    return render_composition(composition, sections)
