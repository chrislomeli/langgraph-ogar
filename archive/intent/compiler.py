"""
Pattern-based compiler: PlanBundle → Composition IR.

First implementation of the PlanCompiler interface. Generates musically
valid NoteEvents, MeasureSpecs, and SectionSpecs using rule-based patterns
driven by the HarmonyPlan, GroovePlan, and VoicePlan.

Design principles:
- Every voice role has a dedicated generator that reads the plan.
- Patterns are simple but musically correct: aligned to harmony, meter, form.
- Output is real domain IR ready for GraphMusicWriter and music21 rendering.
- Designed to be replaced or augmented by LLM-backed generators per voice.

Assumes Pydantic v2.
"""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from fractions import Fraction
from typing import Optional, Sequence

from symbolic_music.domain import (
    ChordEvent as DomainChordEvent,
    CompositionSpec,
    MeasureSpec,
    MeterChange,
    MeterMap,
    NoteEvent,
    Pitch,
    RationalTime,
    RestEvent,
    SectionPlacement,
    SectionSpec,
    TempoChange,
    TempoMap,
    TempoValue,
    TimeSignature,
    TrackConfig,
    TrackSpec,
)

from intent.plan_models import (
    ChordEvent as PlanChordEvent,
    ChordQuality,
    DensityLevel,
    GrooveFeel,
    GrooveSectionPlan,
    HarmonySectionPlan,
    PlanBundle,
    SectionPlan,
    VoiceRole,
    VoiceSpec,
)
from intent.compiler_interface import CompileOptions, CompileResult, PlanCompiler


# ============================================================================
# Musical constants
# ============================================================================

def _rt(n: int, d: int = 1) -> RationalTime:
    return RationalTime(n=n, d=d)


RT_ZERO = _rt(0)
RT_QUARTER = _rt(1, 4)
RT_EIGHTH = _rt(1, 8)
RT_HALF = _rt(1, 2)
RT_WHOLE = _rt(1, 1)
RT_SIXTEENTH = _rt(1, 16)
RT_DOTTED_QUARTER = _rt(3, 8)


# ============================================================================
# Pitch utilities
# ============================================================================

_ROOT_TO_PC: dict[str, int] = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
    "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11, "Cb": 11,
}

_PC_TO_NAME: dict[int, str] = {
    0: "C", 1: "C#", 2: "D", 3: "Eb", 4: "E", 5: "F",
    6: "F#", 7: "G", 8: "Ab", 9: "A", 10: "Bb", 11: "B",
}

_QUALITY_INTERVALS: dict[ChordQuality, tuple[int, ...]] = {
    ChordQuality.maj: (0, 4, 7),
    ChordQuality.min: (0, 3, 7),
    ChordQuality.dim: (0, 3, 6),
    ChordQuality.aug: (0, 4, 8),
    ChordQuality.dom7: (0, 4, 7, 10),
    ChordQuality.maj7: (0, 4, 7, 11),
    ChordQuality.min7: (0, 3, 7, 10),
    ChordQuality.min_maj7: (0, 3, 7, 11),
    ChordQuality.dim7: (0, 3, 6, 9),
    ChordQuality.half_dim7: (0, 3, 6, 10),
    ChordQuality.aug7: (0, 4, 8, 10),
    ChordQuality.sus2: (0, 2, 7),
    ChordQuality.sus4: (0, 5, 7),
    ChordQuality.power: (0, 7),
}


def _chord_pitches(root: str, quality: ChordQuality, octave: int = 4) -> tuple[int, ...]:
    """Return MIDI note numbers for a chord in a given octave."""
    root_pc = _ROOT_TO_PC.get(root, 0)
    base_midi = root_pc + (octave + 1) * 12  # MIDI: C4 = 60
    intervals = _QUALITY_INTERVALS.get(quality, (0, 4, 7))
    return tuple(base_midi + i for i in intervals)


def _root_midi(root: str, octave: int = 4) -> int:
    """MIDI note for a root in a given octave."""
    return _ROOT_TO_PC.get(root, 0) + (octave + 1) * 12


def _parse_time_signature(ts_str: str) -> TimeSignature:
    """Parse '4/4' → TimeSignature(num=4, den=4)."""
    parts = ts_str.strip().split("/")
    return TimeSignature(num=int(parts[0]), den=int(parts[1]))


def _measure_length(ts: TimeSignature) -> RationalTime:
    """Measure length in whole notes."""
    return ts.measure_length_quarters()


# ============================================================================
# Chord lookup for a given bar within a section's harmony
# ============================================================================

def _chord_at_bar(harmony: HarmonySectionPlan, bar: int) -> PlanChordEvent:
    """Get the active chord at a given bar (1-indexed within section)."""
    active = harmony.chords[0]
    for ch in harmony.chords:
        if ch.at_bar <= bar:
            active = ch
        else:
            break
    return active


# ============================================================================
# Section version ID generation (content-addressed)
# ============================================================================

def _section_vid(voice_id: str, section_id: str, content_seed: str) -> str:
    """Generate a deterministic section version ID."""
    payload = json.dumps({"voice": voice_id, "section": section_id, "seed": content_seed}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ============================================================================
# Voice generators — one per role family
# ============================================================================

def _generate_drum_measure(
    bar_in_section: int,
    ts: TimeSignature,
    groove: GrooveSectionPlan,
    rng: random.Random,
) -> MeasureSpec:
    """
    Generate a drum measure.

    Uses GM drum map: kick=36, snare=38, closed_hh=42, open_hh=46, ride=51.
    Pattern varies by density and feel.
    """
    events = []
    ml = _measure_length(ts)
    beats = ts.num

    kick, snare, closed_hh, open_hh, ride = 36, 38, 42, 46, 51

    if groove.feel in (GrooveFeel.bossa, GrooveFeel.samba):
        # Bossa pattern: kick on 1, cross-stick on 3, hats on every beat
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            if beat == 0:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=kick), velocity=100))
            elif beat == 2 and beats >= 4:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=kick), velocity=80))
            # Rim / cross-stick on 2 and 4
            if beat in (1, 3) and beats >= 4:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=snare), velocity=60))
            # Hats on every eighth
            events.append(NoteEvent(offset_q=offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=closed_hh), velocity=70))
            if groove.drum_density != DensityLevel.sparse:
                and_offset = offset + RT_EIGHTH
                if and_offset < ml:
                    events.append(NoteEvent(offset_q=and_offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=closed_hh), velocity=55))
    elif groove.feel == GrooveFeel.swing:
        # Swing: ride pattern with kick/snare comping
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            # Ride on every beat
            events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=ride), velocity=80))
            # Swing eighth on the "and" (triplet feel approximated)
            trip_offset = offset + _rt(1, 6)  # triplet eighth
            if trip_offset < ml:
                events.append(NoteEvent(offset_q=trip_offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=ride), velocity=60))
            # Kick on 1 and 3
            if beat % 2 == 0:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=kick), velocity=90))
            # Snare on 2 and 4 (hi-hat foot)
            if beat % 2 == 1:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=snare), velocity=85))
    else:
        # Standard rock/pop backbeat
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            # Kick on 1 and 3
            if beat % 2 == 0:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=kick), velocity=100))
            # Snare on 2 and 4
            if beat % 2 == 1:
                events.append(NoteEvent(offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=snare), velocity=95))
            # Hi-hat on every eighth
            events.append(NoteEvent(offset_q=offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=closed_hh), velocity=75))
            if groove.drum_density != DensityLevel.sparse:
                and_offset = offset + RT_EIGHTH
                if and_offset < ml:
                    events.append(NoteEvent(offset_q=and_offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=closed_hh), velocity=60))

        # Busy: add extra kick hits
        if groove.drum_density == DensityLevel.busy and beats >= 4:
            extra_offset = _rt(3, ts.den) + RT_EIGHTH
            if extra_offset < ml:
                events.append(NoteEvent(offset_q=extra_offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=kick), velocity=80))

    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=tuple(events),
    )


def _generate_bass_measure(
    bar_in_section: int,
    ts: TimeSignature,
    chord: PlanChordEvent,
    groove: GrooveSectionPlan,
    rng: random.Random,
) -> MeasureSpec:
    """
    Generate a bass measure following the chord root.

    Pattern varies by bass_approach from the groove plan.
    """
    events = []
    root = _root_midi(chord.root, octave=2)  # bass register
    fifth = root + 7
    ml = _measure_length(ts)
    beats = ts.num

    approach = groove.bass_approach or "root-fifth"

    if approach == "pedal":
        # Whole note on root
        events.append(NoteEvent(
            offset_q=RT_ZERO, dur_q=ml, pitch=Pitch(midi=root), velocity=90,
        ))
    elif approach == "walking":
        # Walking bass: root, passing tone, fifth, approach
        scale_tones = [root, root + 2, root + 4, fifth]
        for beat in range(min(beats, len(scale_tones))):
            offset = _rt(beat, ts.den)
            midi = scale_tones[beat % len(scale_tones)]
            midi = max(0, min(127, midi))
            events.append(NoteEvent(
                offset_q=offset, dur_q=RT_QUARTER, pitch=Pitch(midi=midi), velocity=85,
            ))
    elif approach == "bossa":
        # Bossa bass: root on 1, fifth on the "and" of 2
        events.append(NoteEvent(
            offset_q=RT_ZERO, dur_q=RT_DOTTED_QUARTER, pitch=Pitch(midi=root), velocity=90,
        ))
        if beats >= 3:
            events.append(NoteEvent(
                offset_q=_rt(3, 8), dur_q=RT_QUARTER, pitch=Pitch(midi=fifth), velocity=75,
            ))
        if beats >= 4:
            events.append(NoteEvent(
                offset_q=_rt(5, 8), dur_q=RT_DOTTED_QUARTER, pitch=Pitch(midi=root), velocity=80,
            ))
    elif approach == "syncopated":
        # Syncopated: root on 1, rest, root on "and" of 2, fifth on 4
        events.append(NoteEvent(
            offset_q=RT_ZERO, dur_q=RT_EIGHTH, pitch=Pitch(midi=root), velocity=95,
        ))
        if beats >= 3:
            events.append(NoteEvent(
                offset_q=_rt(1, ts.den) + RT_EIGHTH, dur_q=RT_EIGHTH, pitch=Pitch(midi=root), velocity=80,
            ))
        if beats >= 4:
            events.append(NoteEvent(
                offset_q=_rt(3, ts.den), dur_q=RT_QUARTER, pitch=Pitch(midi=fifth), velocity=85,
            ))
    else:
        # Default root-fifth pattern
        events.append(NoteEvent(
            offset_q=RT_ZERO, dur_q=RT_QUARTER, pitch=Pitch(midi=root), velocity=90,
        ))
        if beats >= 2:
            events.append(NoteEvent(
                offset_q=_rt(1, ts.den), dur_q=RT_QUARTER, pitch=Pitch(midi=root), velocity=75,
            ))
        if beats >= 3:
            events.append(NoteEvent(
                offset_q=_rt(2, ts.den), dur_q=RT_QUARTER, pitch=Pitch(midi=fifth), velocity=85,
            ))
        if beats >= 4:
            events.append(NoteEvent(
                offset_q=_rt(3, ts.den), dur_q=RT_QUARTER, pitch=Pitch(midi=root), velocity=70,
            ))

    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=tuple(events),
    )


def _generate_keys_measure(
    bar_in_section: int,
    ts: TimeSignature,
    chord: PlanChordEvent,
    groove: GrooveSectionPlan,
    density: DensityLevel,
    rng: random.Random,
) -> MeasureSpec:
    """
    Generate a keys/piano measure with chord voicings.

    Sparse: whole-note block chords.
    Medium: half-note comping.
    Busy: quarter-note rhythmic comping.
    """
    events = []
    pitches = _chord_pitches(chord.root, chord.quality, octave=4)
    ml = _measure_length(ts)

    if density == DensityLevel.sparse:
        # Whole-note block chord
        chord_pitches = tuple(Pitch(midi=max(0, min(127, m))) for m in pitches)
        if len(chord_pitches) >= 2:
            events.append(DomainChordEvent(
                offset_q=RT_ZERO, dur_q=ml, pitches=chord_pitches, velocity=70,
            ))
        else:
            events.append(NoteEvent(
                offset_q=RT_ZERO, dur_q=ml, pitch=chord_pitches[0], velocity=70,
            ))
    elif density == DensityLevel.busy:
        # Quarter-note comping
        beats = ts.num
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            vel = 75 if beat % 2 == 0 else 60
            chord_pitches = tuple(Pitch(midi=max(0, min(127, m))) for m in pitches)
            if len(chord_pitches) >= 2:
                events.append(DomainChordEvent(
                    offset_q=offset, dur_q=RT_QUARTER, pitches=chord_pitches, velocity=vel,
                ))
            else:
                events.append(NoteEvent(
                    offset_q=offset, dur_q=RT_QUARTER, pitch=chord_pitches[0], velocity=vel,
                ))
    else:
        # Medium: half-note comping
        chord_pitches = tuple(Pitch(midi=max(0, min(127, m))) for m in pitches)
        if len(chord_pitches) >= 2:
            events.append(DomainChordEvent(
                offset_q=RT_ZERO, dur_q=RT_HALF, pitches=chord_pitches, velocity=75,
            ))
            half_offset = RT_HALF
            if half_offset < ml:
                events.append(DomainChordEvent(
                    offset_q=half_offset, dur_q=RT_HALF, pitches=chord_pitches, velocity=65,
                ))
        else:
            events.append(NoteEvent(
                offset_q=RT_ZERO, dur_q=RT_HALF, pitch=chord_pitches[0], velocity=75,
            ))

    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=tuple(events),
    )


def _generate_guitar_measure(
    bar_in_section: int,
    ts: TimeSignature,
    chord: PlanChordEvent,
    groove: GrooveSectionPlan,
    density: DensityLevel,
    rng: random.Random,
) -> MeasureSpec:
    """
    Generate a rhythm guitar measure.

    Power chords in rock, open voicings in other styles.
    """
    events = []
    root_midi = _root_midi(chord.root, octave=3)  # guitar register
    fifth = root_midi + 7
    octave_up = root_midi + 12
    ml = _measure_length(ts)
    beats = ts.num

    # Power chord voicing for rock
    chord_pitches = tuple(Pitch(midi=max(0, min(127, m))) for m in [root_midi, fifth, octave_up])

    if density == DensityLevel.sparse:
        # Whole notes
        events.append(DomainChordEvent(
            offset_q=RT_ZERO, dur_q=ml, pitches=chord_pitches, velocity=70,
        ))
    elif density == DensityLevel.busy:
        # Eighth-note strumming
        for beat in range(beats):
            for sub in range(2):
                offset = _rt(beat, ts.den) + (_rt(0) if sub == 0 else RT_EIGHTH)
                if offset < ml:
                    vel = 80 if sub == 0 else 60
                    events.append(DomainChordEvent(
                        offset_q=offset, dur_q=RT_EIGHTH, pitches=chord_pitches, velocity=vel,
                    ))
    else:
        # Quarter-note downstrokes
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            vel = 80 if beat % 2 == 0 else 65
            events.append(DomainChordEvent(
                offset_q=offset, dur_q=RT_QUARTER, pitches=chord_pitches, velocity=vel,
            ))

    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=tuple(events),
    )


def _generate_pad_measure(
    bar_in_section: int,
    ts: TimeSignature,
    chord: PlanChordEvent,
    density: DensityLevel,
    rng: random.Random,
) -> MeasureSpec:
    """Generate a pad/strings measure — sustained chord voicings."""
    pitches = _chord_pitches(chord.root, chord.quality, octave=4)
    ml = _measure_length(ts)
    chord_pitches = tuple(Pitch(midi=max(0, min(127, m))) for m in pitches)

    events = []
    if len(chord_pitches) >= 2:
        events.append(DomainChordEvent(
            offset_q=RT_ZERO, dur_q=ml, pitches=chord_pitches,
            velocity=50 if density == DensityLevel.sparse else 65,
        ))
    else:
        events.append(NoteEvent(
            offset_q=RT_ZERO, dur_q=ml, pitch=chord_pitches[0], velocity=55,
        ))

    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=tuple(events),
    )


def _generate_percussion_measure(
    bar_in_section: int,
    ts: TimeSignature,
    groove: GrooveSectionPlan,
    rng: random.Random,
) -> MeasureSpec:
    """
    Generate a latin percussion measure.

    Uses GM percussion: conga_hi=62, conga_lo=63, shaker=70, guiro=73.
    """
    events = []
    beats = ts.num
    ml = _measure_length(ts)
    conga_hi, conga_lo, shaker = 62, 63, 70

    if groove.perc_density == DensityLevel.sparse:
        # Shaker on every beat
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            events.append(NoteEvent(
                offset_q=offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=shaker), velocity=50,
            ))
    elif groove.perc_density == DensityLevel.busy:
        # Full conga pattern
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            events.append(NoteEvent(
                offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=conga_hi), velocity=70,
            ))
            and_offset = offset + RT_EIGHTH
            if and_offset < ml:
                events.append(NoteEvent(
                    offset_q=and_offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=conga_lo), velocity=55,
                ))
            events.append(NoteEvent(
                offset_q=offset, dur_q=RT_SIXTEENTH, pitch=Pitch(midi=shaker), velocity=45,
            ))
    else:
        # Medium: alternating congas on beats
        for beat in range(beats):
            offset = _rt(beat, ts.den)
            midi = conga_hi if beat % 2 == 0 else conga_lo
            events.append(NoteEvent(
                offset_q=offset, dur_q=RT_EIGHTH, pitch=Pitch(midi=midi), velocity=65,
            ))

    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=tuple(events),
    )


def _generate_rest_measure(
    bar_in_section: int,
    ts: TimeSignature,
) -> MeasureSpec:
    """Generate a measure of rest (for voices not active in a section)."""
    ml = _measure_length(ts)
    return MeasureSpec(
        local_time_signature=ts if bar_in_section == 1 else None,
        events=(RestEvent(offset_q=RT_ZERO, dur_q=ml),),
    )


# ============================================================================
# Section generator — dispatches to voice generators per measure
# ============================================================================

def _generate_section_for_voice(
    voice: VoiceSpec,
    section: SectionPlan,
    harmony: HarmonySectionPlan,
    groove: GrooveSectionPlan,
    rng: random.Random,
) -> SectionSpec:
    """Generate a complete SectionSpec for one voice in one section."""
    ts = _parse_time_signature(section.time_signature)
    measures = []

    for bar in range(1, section.bars + 1):
        chord = _chord_at_bar(harmony, bar)

        if voice.role == VoiceRole.drums:
            m = _generate_drum_measure(bar, ts, groove, rng)
        elif voice.role == VoiceRole.bass:
            m = _generate_bass_measure(bar, ts, chord, groove, rng)
        elif voice.role in (VoiceRole.keys, VoiceRole.woodwinds):
            m = _generate_keys_measure(bar, ts, chord, groove, section.density, rng)
        elif voice.role in (VoiceRole.rhythm_guitar, VoiceRole.acoustic_guitar, VoiceRole.lead_guitar):
            m = _generate_guitar_measure(bar, ts, chord, groove, section.density, rng)
        elif voice.role in (VoiceRole.pad, VoiceRole.strings):
            m = _generate_pad_measure(bar, ts, chord, section.density, rng)
        elif voice.role == VoiceRole.percussion:
            m = _generate_percussion_measure(bar, ts, groove, rng)
        else:
            # Default: chord comping
            m = _generate_keys_measure(bar, ts, chord, groove, section.density, rng)

        measures.append(m)

    section_name = f"{voice.name} - {section.section_id}"
    return SectionSpec(name=section_name, measures=tuple(measures))


# ============================================================================
# PatternCompiler — the main compiler
# ============================================================================

class PatternCompiler(PlanCompiler):
    """
    Rule-based compiler: PlanBundle → CompileResult.

    Generates per-voice SectionSpecs for each section in the FormPlan,
    assembles TrackSpecs with SectionPlacements, and builds the
    CompositionSpec with MeterMap and TempoMap.

    Usage:
        >>> compiler = PatternCompiler()
        >>> result = compiler.compile(plan)
        >>> result.composition  # CompositionSpec
        >>> result.sections     # dict[svid, SectionSpec]
    """

    def compile(
        self,
        plan: PlanBundle,
        options: Optional[CompileOptions] = None,
        previous: Optional[CompileResult] = None,
    ) -> CompileResult:
        opts = options or CompileOptions()
        rng = random.Random(opts.seed if opts.seed is not None else 42)
        warnings: list[str] = []

        # --- Build MeterMap ---
        # Collect unique time signatures from sections on the timeline
        meter_changes = []
        section_map = {s.section_id: s for s in plan.form_plan.sections}
        seen_ts: Optional[str] = None

        for tp in plan.form_plan.timeline:
            sp = section_map.get(tp.section_id)
            if sp and sp.time_signature != seen_ts:
                meter_changes.append(MeterChange(
                    at_bar=tp.start_bar,
                    ts=_parse_time_signature(sp.time_signature),
                ))
                seen_ts = sp.time_signature

        if not meter_changes:
            meter_changes.append(MeterChange(at_bar=1, ts=_parse_time_signature(plan.time_signature)))

        # Ensure first change is at bar 1
        if meter_changes[0].at_bar != 1:
            meter_changes.insert(0, MeterChange(at_bar=1, ts=_parse_time_signature(plan.time_signature)))

        meter_map = MeterMap(changes=tuple(meter_changes))

        # --- Build TempoMap ---
        tempo_changes = [
            TempoChange(
                at_bar=1,
                at_beat=1,
                tempo=TempoValue(bpm=_rt(int(plan.tempo_bpm)), beat_unit_den=4),
            )
        ]
        # Add section-level tempo overrides
        for tp in plan.form_plan.timeline:
            sp = section_map.get(tp.section_id)
            if sp and sp.tempo_bpm and sp.tempo_bpm != plan.tempo_bpm:
                tempo_changes.append(TempoChange(
                    at_bar=tp.start_bar,
                    at_beat=1,
                    tempo=TempoValue(bpm=_rt(int(sp.tempo_bpm)), beat_unit_den=4),
                ))

        tempo_map = TempoMap(changes=tuple(tempo_changes))

        # --- Generate sections per voice ---
        sections_by_svid: dict[str, SectionSpec] = {}
        tracks: list[TrackSpec] = []

        for voice in plan.voice_plan.voices:
            # Check scoped regeneration
            if opts.regenerate_voices and voice.voice_id not in opts.regenerate_voices:
                # Preserve from previous result
                if previous:
                    prev_track = previous.composition.get_track(voice.voice_id)
                    if prev_track:
                        tracks.append(prev_track)
                        # Also preserve sections
                        for pl in prev_track.placements:
                            if pl.section_version_id in previous.sections:
                                sections_by_svid[pl.section_version_id] = previous.sections[pl.section_version_id]
                        continue
                warnings.append(f"Scoped regen: no previous result for voice '{voice.voice_id}', regenerating.")

            placements: list[SectionPlacement] = []

            for tp in plan.form_plan.timeline:
                sp = section_map.get(tp.section_id)
                if not sp:
                    warnings.append(f"Timeline references unknown section: {tp.section_id}")
                    continue

                # Check section participation
                active_voices = plan.voice_plan.voices_for_section(sp.section_id)
                if voice not in active_voices:
                    continue

                # Check scoped section regeneration
                if opts.regenerate_sections and sp.section_id not in opts.regenerate_sections:
                    if previous:
                        # Find existing svid for this voice+section
                        prev_track = previous.composition.get_track(voice.voice_id)
                        if prev_track:
                            for prev_pl in prev_track.placements:
                                if prev_pl.start_bar == tp.start_bar and prev_pl.section_version_id in previous.sections:
                                    placements.append(prev_pl)
                                    sections_by_svid[prev_pl.section_version_id] = previous.sections[prev_pl.section_version_id]
                                    break
                            continue

                # Get harmony and groove for this section
                harmony = plan.harmony_plan.get_section(sp.section_id)
                groove = plan.groove_plan.get_section(sp.section_id)

                if not harmony:
                    warnings.append(f"No harmony for section '{sp.section_id}', using defaults.")
                    harmony = HarmonySectionPlan(
                        section_id=sp.section_id,
                        key=plan.key,
                        chords=(PlanChordEvent(at_bar=1, root="C", quality=ChordQuality.maj),),
                    )
                if not groove:
                    groove = GrooveSectionPlan(section_id=sp.section_id)

                # Generate the section
                section_spec = _generate_section_for_voice(voice, sp, harmony, groove, rng)

                # Generate deterministic svid
                svid = _section_vid(voice.voice_id, sp.section_id, str(rng.random()))
                sections_by_svid[svid] = section_spec

                placements.append(SectionPlacement(
                    section_version_id=svid,
                    start_bar=tp.start_bar,
                    repeats=tp.repeats,
                ))

            # Determine clef
            clef = voice.clef
            if not clef:
                if voice.role == VoiceRole.bass:
                    clef = "bass"
                elif voice.role == VoiceRole.drums:
                    clef = None  # percussion
                else:
                    clef = "treble"

            track = TrackSpec(
                track_id=voice.voice_id,
                config=TrackConfig(
                    name=voice.name,
                    instrument_hint=voice.instrument,
                    midi_channel=voice.midi_channel,
                    clef=clef,
                ),
                placements=tuple(placements),
            )
            tracks.append(track)

        # --- Assemble CompositionSpec ---
        composition = CompositionSpec(
            title=plan.title,
            meter_map=meter_map,
            tempo_map=tempo_map,
            tracks=tuple(tracks),
        )

        return CompileResult(
            composition=composition,
            sections=sections_by_svid,
            warnings=warnings,
            plan_bundle_id=plan.bundle_id,
        )
