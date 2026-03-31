"""
Deterministic engine: Sketch → PlanBundle.

This is the first, rule-based implementation of the planning interface.
It makes musically reasonable defaults from the sketch's free-text prompt
and structured hints. Designed to be replaced by an LLM-backed engine
without changing the contract.

Design principles:
- Produces a complete, valid PlanBundle from any valid Sketch.
- Genre/style keywords drive voice roster, groove feel, and harmony defaults.
- Structured hints (key, tempo, form) override inferred values.
- Every decision is traceable: the engine logs its reasoning.

Assumes Pydantic v2.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional, Sequence

from intent.sketch_models import Sketch, VoiceHint
from intent.plan_models import (
    ChordEvent,
    ChordQuality,
    DensityLevel,
    EnergyLevel,
    FormPlan,
    GrooveFeel,
    GroovePlan,
    GrooveSectionPlan,
    HarmonyPlan,
    HarmonySectionPlan,
    PlanBundle,
    RenderPlan,
    SectionPlan,
    SectionRole,
    TimelinePlacement,
    VoicePlan,
    VoiceRole,
    VoiceSpec,
)


# ============================================================================
# Genre profiles — default musical decisions keyed by genre
# ============================================================================

_GENRE_DEFAULTS: dict[str, dict] = {
    "rock": {
        "tempo": 120,
        "key": "E minor",
        "time_signature": "4/4",
        "feel": GrooveFeel.straight,
        "voices": [
            ("drums", VoiceRole.drums, "drum_kit"),
            ("bass", VoiceRole.bass, "electric_bass"),
            ("rhythm_guitar", VoiceRole.rhythm_guitar, "electric_guitar"),
            ("lead_guitar", VoiceRole.lead_guitar, "electric_guitar"),
        ],
        "energy_arc": {
            SectionRole.intro: EnergyLevel.low,
            SectionRole.verse: EnergyLevel.medium,
            SectionRole.prechorus: EnergyLevel.high,
            SectionRole.chorus: EnergyLevel.very_high,
            SectionRole.bridge: EnergyLevel.medium,
            SectionRole.solo: EnergyLevel.very_high,
            SectionRole.outro: EnergyLevel.low,
        },
        "chord_map": {
            "minor": [
                ("i", "min"), ("iv", "min"), ("VII", "maj"), ("III", "maj"),
                ("VI", "maj"), ("v", "min"), ("iv", "min"), ("i", "min"),
            ],
            "major": [
                ("I", "maj"), ("IV", "maj"), ("V", "maj"), ("I", "maj"),
                ("vi", "min"), ("IV", "maj"), ("V", "maj"), ("I", "maj"),
            ],
        },
    },
    "pop": {
        "tempo": 110,
        "key": "C major",
        "time_signature": "4/4",
        "feel": GrooveFeel.straight,
        "voices": [
            ("drums", VoiceRole.drums, "drum_kit"),
            ("bass", VoiceRole.bass, "electric_bass"),
            ("keys", VoiceRole.keys, "piano"),
            ("pad", VoiceRole.pad, "strings"),
        ],
        "energy_arc": {
            SectionRole.intro: EnergyLevel.low,
            SectionRole.verse: EnergyLevel.medium,
            SectionRole.prechorus: EnergyLevel.high,
            SectionRole.chorus: EnergyLevel.very_high,
            SectionRole.bridge: EnergyLevel.medium,
            SectionRole.outro: EnergyLevel.medium,
        },
        "chord_map": {
            "minor": [
                ("i", "min"), ("VI", "maj"), ("III", "maj"), ("VII", "maj"),
                ("i", "min"), ("iv", "min"), ("VII", "maj"), ("i", "min"),
            ],
            "major": [
                ("I", "maj"), ("V", "maj"), ("vi", "min"), ("IV", "maj"),
                ("I", "maj"), ("V", "maj"), ("vi", "min"), ("IV", "maj"),
            ],
        },
    },
    "jazz": {
        "tempo": 140,
        "key": "Bb major",
        "time_signature": "4/4",
        "feel": GrooveFeel.swing,
        "voices": [
            ("drums", VoiceRole.drums, "drum_kit"),
            ("bass", VoiceRole.bass, "acoustic_bass"),
            ("keys", VoiceRole.keys, "piano"),
            ("sax", VoiceRole.woodwinds, "tenor_sax"),
        ],
        "energy_arc": {
            SectionRole.intro: EnergyLevel.low,
            SectionRole.verse: EnergyLevel.medium,
            SectionRole.chorus: EnergyLevel.high,
            SectionRole.bridge: EnergyLevel.medium,
            SectionRole.solo: EnergyLevel.high,
            SectionRole.outro: EnergyLevel.low,
        },
        "chord_map": {
            "minor": [
                ("i", "min7"), ("iv", "min7"), ("V", "dom7"), ("i", "min7"),
                ("VI", "maj7"), ("ii", "half_dim7"), ("V", "dom7"), ("i", "min7"),
            ],
            "major": [
                ("I", "maj7"), ("vi", "min7"), ("ii", "min7"), ("V", "dom7"),
                ("I", "maj7"), ("IV", "maj7"), ("ii", "min7"), ("V", "dom7"),
            ],
        },
    },
    "ballad": {
        "tempo": 72,
        "key": "G major",
        "time_signature": "4/4",
        "feel": GrooveFeel.straight,
        "voices": [
            ("drums", VoiceRole.drums, "drum_kit"),
            ("bass", VoiceRole.bass, "acoustic_bass"),
            ("keys", VoiceRole.keys, "piano"),
        ],
        "energy_arc": {
            SectionRole.intro: EnergyLevel.very_low,
            SectionRole.verse: EnergyLevel.low,
            SectionRole.chorus: EnergyLevel.medium,
            SectionRole.bridge: EnergyLevel.high,
            SectionRole.outro: EnergyLevel.very_low,
        },
        "chord_map": {
            "minor": [
                ("i", "min"), ("VI", "maj"), ("III", "maj"), ("VII", "maj"),
                ("iv", "min"), ("i", "min"), ("V", "dom7"), ("i", "min"),
            ],
            "major": [
                ("I", "maj"), ("iii", "min"), ("vi", "min"), ("IV", "maj"),
                ("I", "maj"), ("V", "maj"), ("IV", "maj"), ("I", "maj"),
            ],
        },
    },
}

# Fallback if genre not recognized
_DEFAULT_GENRE = "rock"


# ============================================================================
# Form templates — common song structures
# ============================================================================

_FORM_TEMPLATES: dict[str, list[tuple[str, SectionRole, int]]] = {
    "verse-chorus": [
        ("intro", SectionRole.intro, 4),
        ("verse1", SectionRole.verse, 8),
        ("chorus1", SectionRole.chorus, 8),
        ("verse2", SectionRole.verse, 8),
        ("chorus2", SectionRole.chorus, 8),
        ("outro", SectionRole.outro, 4),
    ],
    "verse-chorus-bridge": [
        ("intro", SectionRole.intro, 4),
        ("verse1", SectionRole.verse, 8),
        ("chorus1", SectionRole.chorus, 8),
        ("verse2", SectionRole.verse, 8),
        ("chorus2", SectionRole.chorus, 8),
        ("bridge", SectionRole.bridge, 8),
        ("chorus3", SectionRole.chorus, 8),
        ("outro", SectionRole.outro, 4),
    ],
    "verse-chorus-verse": [
        ("intro", SectionRole.intro, 4),
        ("verse1", SectionRole.verse, 8),
        ("chorus1", SectionRole.chorus, 8),
        ("verse2", SectionRole.verse, 8),
        ("chorus2", SectionRole.chorus, 8),
        ("outro", SectionRole.outro, 4),
    ],
    "aaba": [
        ("a1", SectionRole.verse, 8),
        ("a2", SectionRole.verse, 8),
        ("b", SectionRole.bridge, 8),
        ("a3", SectionRole.verse, 8),
    ],
    "simple": [
        ("verse1", SectionRole.verse, 8),
        ("chorus1", SectionRole.chorus, 8),
        ("verse2", SectionRole.verse, 8),
        ("chorus2", SectionRole.chorus, 8),
    ],
}

_DEFAULT_FORM = "verse-chorus-bridge"


# ============================================================================
# Key / scale utilities
# ============================================================================

_NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]

_SCALE_INTERVALS = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "minor": [0, 2, 3, 5, 7, 8, 10],
}


def _parse_key(key_str: str) -> tuple[str, str]:
    """Parse 'A minor' → ('A', 'minor'), 'Bb major' → ('Bb', 'major')."""
    parts = key_str.strip().split()
    if len(parts) >= 2:
        root = parts[0]
        mode = parts[1].lower()
        if mode not in ("major", "minor"):
            mode = "major"
        return root, mode
    return parts[0] if parts else "C", "major"


def _root_to_midi(root: str) -> int:
    """Map root note name to MIDI pitch class (0-11)."""
    mapping = {
        "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
        "E": 4, "Fb": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7,
        "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11, "Cb": 11,
    }
    return mapping.get(root, 0)


def _scale_degree_to_root(key_root: str, mode: str, degree_roman: str) -> str:
    """
    Convert a roman numeral scale degree to a root note name.

    E.g., in A minor: 'i' → 'A', 'III' → 'C', 'VII' → 'G'
    """
    degree_map_major = {
        "I": 0, "ii": 1, "iii": 2, "IV": 3, "V": 4, "vi": 5, "vii": 6,
        "i": 0, "II": 1, "III": 2, "iv": 3, "v": 4, "VI": 5, "VII": 6,
    }
    degree_map_minor = {
        "i": 0, "ii": 1, "III": 2, "iv": 3, "v": 4, "VI": 5, "VII": 6,
        "I": 0, "II": 1, "iii": 2, "IV": 3, "V": 4, "vi": 5, "vii": 6,
    }

    degree_map = degree_map_minor if mode == "minor" else degree_map_major
    # Strip any quality suffix that might have leaked in
    clean_degree = degree_roman.rstrip("0123456789")
    scale_idx = degree_map.get(clean_degree, 0)

    intervals = _SCALE_INTERVALS[mode]
    root_pc = _root_to_midi(key_root)
    note_pc = (root_pc + intervals[scale_idx]) % 12
    return _NOTE_NAMES[note_pc]


# ============================================================================
# Prompt parsing — extract structured hints from free text
# ============================================================================

def _detect_genre(prompt: str) -> str:
    """Detect genre from prompt keywords."""
    lower = prompt.lower()
    for genre in ["jazz", "ballad", "pop", "rock"]:
        if genre in lower:
            return genre
    return _DEFAULT_GENRE


def _detect_feel(prompt: str) -> Optional[GrooveFeel]:
    """Detect groove feel modifiers from prompt."""
    lower = prompt.lower()
    feel_keywords = {
        "bossa": GrooveFeel.bossa,
        "samba": GrooveFeel.samba,
        "swing": GrooveFeel.swing,
        "shuffle": GrooveFeel.shuffle,
        "halftime": GrooveFeel.halftime,
        "half-time": GrooveFeel.halftime,
        "double-time": GrooveFeel.doubletime,
        "doubletime": GrooveFeel.doubletime,
    }
    for keyword, feel in feel_keywords.items():
        if keyword in lower:
            return feel
    return None


def _detect_form(prompt: str) -> Optional[str]:
    """Detect form template from prompt."""
    lower = prompt.lower()
    if "aaba" in lower:
        return "aaba"
    # Count section mentions to pick a template
    has_bridge = "bridge" in lower
    has_verse = "verse" in lower
    has_chorus = "chorus" in lower

    if has_bridge:
        return "verse-chorus-bridge"
    if has_verse and has_chorus:
        return "verse-chorus"
    return None


def _detect_key(prompt: str) -> Optional[str]:
    """Detect key from prompt, e.g. 'A minor', 'key of C'."""
    lower = prompt.lower()
    # Pattern: "key of X" or "X major/minor"
    key_of = re.search(r"key\s+of\s+([a-g][#b]?\s*(?:major|minor)?)", lower)
    if key_of:
        return key_of.group(1).strip().title()

    explicit = re.search(r"([a-g][#b]?)\s+(major|minor)", lower)
    if explicit:
        root = explicit.group(1).upper()
        if root.endswith("b"):
            root = root[:-1] + "b"
        mode = explicit.group(2)
        return f"{root} {mode}"

    return None


def _detect_tempo(prompt: str) -> Optional[float]:
    """Detect tempo from prompt, e.g. '120 bpm', 'tempo 90'."""
    match = re.search(r"(\d{2,3})\s*bpm", prompt.lower())
    if match:
        return float(match.group(1))
    match = re.search(r"tempo\s+(\d{2,3})", prompt.lower())
    if match:
        return float(match.group(1))
    return None


def _detect_time_signature(prompt: str) -> Optional[str]:
    """Detect time signature from prompt, e.g. '6/8', '3/4'."""
    match = re.search(r"(\d)/(\d)", prompt)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return None


# ============================================================================
# Voice roster construction
# ============================================================================

def _build_voice_roster(
    genre_voices: list[tuple[str, VoiceRole, str]],
    voice_hints: Sequence[VoiceHint],
    avoid: Sequence[str],
    feel: GrooveFeel,
) -> list[VoiceSpec]:
    """
    Build the voice roster from genre defaults + user hints.

    Required hints are always included. Preferred hints are added if not
    already covered by genre defaults. Genre defaults are included unless
    the user explicitly avoids them.
    """
    avoid_lower = {a.lower() for a in avoid}
    voices: dict[str, VoiceSpec] = {}
    channel = 1

    # Start with genre defaults
    for name, role, instrument in genre_voices:
        if name.lower() in avoid_lower or instrument.lower() in avoid_lower:
            continue
        vid = f"{name}-{uuid.uuid4().hex[:6]}"
        voices[name] = VoiceSpec(
            voice_id=vid,
            name=name.replace("_", " ").title(),
            role=role,
            instrument=instrument,
            midi_channel=min(channel, 16),
        )
        channel += 1

    # Add bossa/latin percussion if feel calls for it
    if feel in (GrooveFeel.bossa, GrooveFeel.samba, GrooveFeel.clave_2_3, GrooveFeel.clave_3_2):
        if "percussion" not in voices:
            vid = f"percussion-{uuid.uuid4().hex[:6]}"
            voices["percussion"] = VoiceSpec(
                voice_id=vid,
                name="Latin Percussion",
                role=VoiceRole.percussion,
                instrument="congas",
                midi_channel=min(channel, 16),
                default_density=DensityLevel.sparse,
            )
            channel += 1

    # Layer in user hints
    for hint in voice_hints:
        hint_lower = hint.name.lower()
        if hint_lower in avoid_lower:
            continue

        # Check if already covered
        already_covered = any(
            hint_lower in v.name.lower() or hint_lower in v.instrument.lower()
            for v in voices.values()
        )

        if hint.importance == "required" or (hint.importance == "preferred" and not already_covered):
            if hint_lower not in voices:
                vid = f"{hint_lower.replace(' ', '_')}-{uuid.uuid4().hex[:6]}"
                # Infer role from name
                role = _infer_role(hint_lower)
                voices[hint_lower] = VoiceSpec(
                    voice_id=vid,
                    name=hint.name.title(),
                    role=role,
                    instrument=hint_lower.replace(" ", "_"),
                    midi_channel=min(channel, 16),
                    notes=hint.notes,
                )
                channel += 1

    return list(voices.values())


def _infer_role(name: str) -> VoiceRole:
    """Infer VoiceRole from an instrument/voice name."""
    name = name.lower()
    role_keywords = {
        "drum": VoiceRole.drums,
        "percussion": VoiceRole.percussion,
        "conga": VoiceRole.percussion,
        "bongo": VoiceRole.percussion,
        "shaker": VoiceRole.percussion,
        "bass": VoiceRole.bass,
        "guitar": VoiceRole.rhythm_guitar,
        "lead guitar": VoiceRole.lead_guitar,
        "acoustic guitar": VoiceRole.acoustic_guitar,
        "piano": VoiceRole.keys,
        "keys": VoiceRole.keys,
        "keyboard": VoiceRole.keys,
        "organ": VoiceRole.keys,
        "pad": VoiceRole.pad,
        "synth": VoiceRole.pad,
        "string": VoiceRole.strings,
        "violin": VoiceRole.strings,
        "cello": VoiceRole.strings,
        "brass": VoiceRole.brass,
        "trumpet": VoiceRole.brass,
        "trombone": VoiceRole.brass,
        "horn": VoiceRole.brass,
        "sax": VoiceRole.woodwinds,
        "flute": VoiceRole.woodwinds,
        "clarinet": VoiceRole.woodwinds,
        "oboe": VoiceRole.woodwinds,
        "vocal": VoiceRole.vox_lead,
        "voice": VoiceRole.vox_lead,
        "vox": VoiceRole.vox_lead,
        "harmony vocal": VoiceRole.vox_harmony,
    }
    for keyword, role in role_keywords.items():
        if keyword in name:
            return role
    return VoiceRole.keys  # safe default


# ============================================================================
# Harmony generation
# ============================================================================

def _build_harmony_for_section(
    section: SectionPlan,
    key_root: str,
    mode: str,
    chord_map: list[tuple[str, str]],
) -> HarmonySectionPlan:
    """
    Generate a chord progression for a section based on genre defaults.

    Distributes chords evenly across the section's bars, cycling the
    chord_map pattern as needed.
    """
    chords: list[ChordEvent] = []
    num_chords = len(chord_map)

    for bar in range(1, section.bars + 1):
        chord_idx = (bar - 1) % num_chords
        degree_roman, quality_str = chord_map[chord_idx]
        root = _scale_degree_to_root(key_root, mode, degree_roman)
        quality = ChordQuality(quality_str) if quality_str in ChordQuality.__members__ else ChordQuality.maj
        chords.append(ChordEvent(at_bar=bar, at_beat=1.0, root=root, quality=quality))

    return HarmonySectionPlan(
        section_id=section.section_id,
        key=f"{key_root} {mode}",
        chords=tuple(chords),
    )


# ============================================================================
# The Planner
# ============================================================================

class DeterministicPlanner:
    """
    Rule-based engine: Sketch → PlanBundle.

    Implements the engine interface using genre profiles, form templates,
    and prompt parsing. Designed to be swapped for an LLM-backed engine
    without changing the contract.

    Usage:
        >>> engine = DeterministicPlanner()
        >>> plan = engine.plan(Sketch(prompt="Rock tune, bossa groove, A minor"))
    """

    def plan(self, sketch: Sketch) -> PlanBundle:
        """Produce a complete PlanBundle from a Sketch."""

        # --- Extract intent from prompt + structured hints ---
        genre = _detect_genre(sketch.prompt)
        profile = _GENRE_DEFAULTS.get(genre, _GENRE_DEFAULTS[_DEFAULT_GENRE])

        feel_override = _detect_feel(sketch.prompt)
        feel = feel_override or profile["feel"]

        key = sketch.key or _detect_key(sketch.prompt) or profile["key"]
        key_root, mode = _parse_key(key)

        tempo = sketch.tempo_bpm or _detect_tempo(sketch.prompt) or profile["tempo"]
        time_sig = sketch.time_signature or _detect_time_signature(sketch.prompt) or profile["time_signature"]

        title = sketch.title or f"Untitled {genre.title()} Composition"

        # --- Form ---
        form_key = _detect_form(sketch.prompt) or (sketch.form_hint or "").lower().strip()
        if form_key not in _FORM_TEMPLATES:
            # Try to match partial form hints
            for template_key in _FORM_TEMPLATES:
                if template_key in form_key or form_key in template_key:
                    form_key = template_key
                    break
            else:
                form_key = _DEFAULT_FORM

        form_template = _FORM_TEMPLATES[form_key]
        energy_arc = profile["energy_arc"]

        section_plans = []
        timeline_placements = []
        current_bar = 1

        for section_id, role, bars in form_template:
            energy = energy_arc.get(role, EnergyLevel.medium)
            density = DensityLevel.medium
            if energy in (EnergyLevel.very_low, EnergyLevel.low):
                density = DensityLevel.sparse
            elif energy in (EnergyLevel.high, EnergyLevel.very_high):
                density = DensityLevel.busy

            section_plans.append(SectionPlan(
                section_id=section_id,
                role=role,
                bars=bars,
                time_signature=time_sig,
                energy=energy,
                density=density,
            ))
            timeline_placements.append(TimelinePlacement(
                section_id=section_id,
                start_bar=current_bar,
                repeats=1,
            ))
            current_bar += bars

        form_plan = FormPlan(
            sections=tuple(section_plans),
            timeline=tuple(timeline_placements),
        )

        # --- Voices ---
        voice_specs = _build_voice_roster(
            genre_voices=profile["voices"],
            voice_hints=sketch.voice_hints,
            avoid=sketch.avoid,
            feel=feel,
        )
        voice_plan = VoicePlan(voices=tuple(voice_specs))

        # --- Harmony ---
        chord_map_key = mode  # "major" or "minor"
        chord_map = profile["chord_map"].get(chord_map_key, profile["chord_map"]["major"])

        harmony_sections = []
        for sp in section_plans:
            harmony_sections.append(
                _build_harmony_for_section(sp, key_root, mode, chord_map)
            )
        harmony_plan = HarmonyPlan(sections=tuple(harmony_sections))

        # --- Groove ---
        groove_sections = []
        for sp in section_plans:
            drum_density = DensityLevel.medium
            perc_density = DensityLevel.sparse
            bass_approach = "root-fifth"

            if sp.energy in (EnergyLevel.very_low, EnergyLevel.low):
                drum_density = DensityLevel.sparse
                bass_approach = "pedal"
            elif sp.energy in (EnergyLevel.high, EnergyLevel.very_high):
                drum_density = DensityLevel.busy
                bass_approach = "syncopated"

            if feel == GrooveFeel.bossa:
                bass_approach = "bossa"
            elif feel == GrooveFeel.swing:
                bass_approach = "walking"

            swing_amount = 0.0
            if feel == GrooveFeel.swing:
                swing_amount = 0.6
            elif feel == GrooveFeel.bossa:
                swing_amount = 0.3
            elif feel == GrooveFeel.shuffle:
                swing_amount = 0.5

            groove_sections.append(GrooveSectionPlan(
                section_id=sp.section_id,
                feel=feel,
                drum_density=drum_density,
                perc_density=perc_density,
                bass_approach=bass_approach,
                swing_amount=swing_amount,
            ))

        groove_plan = GroovePlan(
            global_feel=feel,
            sections=tuple(groove_sections),
        )

        # --- Assemble ---
        bundle_id = f"plan-{uuid.uuid4().hex[:12]}"

        return PlanBundle(
            bundle_id=bundle_id,
            sketch_id=sketch.sketch_id,
            title=title,
            key=f"{key_root} {mode}",
            tempo_bpm=tempo,
            time_signature=time_sig,
            voice_plan=voice_plan,
            form_plan=form_plan,
            harmony_plan=harmony_plan,
            groove_plan=groove_plan,
            render_plan=RenderPlan(),
        )

    def refine(self, plan: PlanBundle, prompt: str) -> PlanBundle:
        """
        Apply a plan-level refinement.

        This deterministic implementation handles common structural tweaks.
        An LLM-backed engine would interpret arbitrary natural language here.
        """
        lower = prompt.lower()

        # --- Add a bridge ---
        if "add" in lower and "bridge" in lower:
            return self._add_bridge(plan)

        # --- Remove a section ---
        remove_match = re.search(r"remove\s+(?:the\s+)?(\w+)", lower)
        if remove_match:
            target = remove_match.group(1)
            return self._remove_section(plan, target)

        # --- Make something busier/sparser ---
        busier_match = re.search(r"(?:make|more)\s+(?:the\s+)?(\w+)\s+busier", lower)
        if busier_match:
            target = busier_match.group(1)
            return self._adjust_density(plan, target, DensityLevel.busy)

        sparser_match = re.search(r"(?:make|more)\s+(?:the\s+)?(\w+)\s+(?:sparser|simpler|quieter)", lower)
        if sparser_match:
            target = sparser_match.group(1)
            return self._adjust_density(plan, target, DensityLevel.sparse)

        # Fallback: return unchanged (LLM engine would handle this)
        return plan

    def _add_bridge(self, plan: PlanBundle) -> PlanBundle:
        """Insert a bridge section before the last chorus."""
        sections = list(plan.form_plan.sections)
        timeline = list(plan.form_plan.timeline)

        # Check if bridge already exists
        if any(s.role == SectionRole.bridge for s in sections):
            return plan

        bridge = SectionPlan(
            section_id="bridge",
            role=SectionRole.bridge,
            bars=8,
            time_signature=plan.time_signature,
            energy=EnergyLevel.medium,
            density=DensityLevel.medium,
        )
        sections.append(bridge)

        # Recalculate timeline: insert bridge before last chorus
        last_chorus_idx = None
        for i in range(len(timeline) - 1, -1, -1):
            sp = plan.form_plan.get_section(timeline[i].section_id)
            if sp and sp.role == SectionRole.chorus:
                last_chorus_idx = i
                break

        if last_chorus_idx is not None:
            # Shift everything from last chorus onward by 8 bars
            new_timeline = list(timeline[:last_chorus_idx])
            bridge_start = timeline[last_chorus_idx].start_bar
            new_timeline.append(TimelinePlacement(
                section_id="bridge",
                start_bar=bridge_start,
            ))
            for tp in timeline[last_chorus_idx:]:
                new_timeline.append(TimelinePlacement(
                    section_id=tp.section_id,
                    start_bar=tp.start_bar + 8,
                    repeats=tp.repeats,
                ))
            timeline = new_timeline

        new_form = FormPlan(
            sections=tuple(sections),
            timeline=tuple(timeline),
        )

        # Add harmony and groove for bridge
        key_root, mode = _parse_key(plan.key)
        genre = _detect_genre(plan.title)
        profile = _GENRE_DEFAULTS.get(genre, _GENRE_DEFAULTS[_DEFAULT_GENRE])
        chord_map = profile["chord_map"].get(mode, profile["chord_map"]["major"])

        bridge_harmony = _build_harmony_for_section(bridge, key_root, mode, chord_map)
        new_harmony = HarmonyPlan(
            sections=tuple(list(plan.harmony_plan.sections) + [bridge_harmony]),
        )

        bridge_groove = GrooveSectionPlan(
            section_id="bridge",
            feel=plan.groove_plan.global_feel,
            drum_density=DensityLevel.medium,
            perc_density=DensityLevel.sparse,
            bass_approach="root-fifth",
        )
        new_groove = GroovePlan(
            global_feel=plan.groove_plan.global_feel,
            sections=tuple(list(plan.groove_plan.sections) + [bridge_groove]),
        )

        return PlanBundle(
            bundle_id=f"plan-{uuid.uuid4().hex[:12]}",
            sketch_id=plan.sketch_id,
            title=plan.title,
            key=plan.key,
            tempo_bpm=plan.tempo_bpm,
            time_signature=plan.time_signature,
            voice_plan=plan.voice_plan,
            form_plan=new_form,
            harmony_plan=new_harmony,
            groove_plan=new_groove,
            render_plan=plan.render_plan,
        )

    def _remove_section(self, plan: PlanBundle, target: str) -> PlanBundle:
        """Remove a section by role name or section_id."""
        target_lower = target.lower()
        remove_ids = set()
        for s in plan.form_plan.sections:
            if s.section_id.lower() == target_lower or s.role.value == target_lower:
                remove_ids.add(s.section_id)

        if not remove_ids:
            return plan

        new_sections = tuple(s for s in plan.form_plan.sections if s.section_id not in remove_ids)
        if not new_sections:
            return plan  # Don't remove everything

        # Rebuild timeline without removed sections, recalculate start bars
        new_timeline_items = []
        current_bar = 1
        section_map = {s.section_id: s for s in new_sections}
        for tp in plan.form_plan.timeline:
            if tp.section_id in remove_ids:
                continue
            sp = section_map.get(tp.section_id)
            if sp:
                new_timeline_items.append(TimelinePlacement(
                    section_id=tp.section_id,
                    start_bar=current_bar,
                    repeats=tp.repeats,
                ))
                current_bar += sp.bars * tp.repeats

        new_form = FormPlan(sections=new_sections, timeline=tuple(new_timeline_items))
        new_harmony = HarmonyPlan(
            sections=tuple(s for s in plan.harmony_plan.sections if s.section_id not in remove_ids),
        )
        new_groove = GroovePlan(
            global_feel=plan.groove_plan.global_feel,
            sections=tuple(s for s in plan.groove_plan.sections if s.section_id not in remove_ids),
        )

        return PlanBundle(
            bundle_id=f"plan-{uuid.uuid4().hex[:12]}",
            sketch_id=plan.sketch_id,
            title=plan.title,
            key=plan.key,
            tempo_bpm=plan.tempo_bpm,
            time_signature=plan.time_signature,
            voice_plan=plan.voice_plan,
            form_plan=new_form,
            harmony_plan=new_harmony,
            groove_plan=new_groove,
            render_plan=plan.render_plan,
        )

    def _adjust_density(self, plan: PlanBundle, target: str, density: DensityLevel) -> PlanBundle:
        """Adjust density for sections or voices matching target."""
        target_lower = target.lower()

        # Try matching section roles
        new_groove_sections = []
        changed = False
        for gs in plan.groove_plan.sections:
            sp = plan.form_plan.get_section(gs.section_id)
            if sp and (sp.role.value == target_lower or sp.section_id.lower() == target_lower):
                new_groove_sections.append(GrooveSectionPlan(
                    section_id=gs.section_id,
                    feel=gs.feel,
                    drum_density=density,
                    perc_density=density,
                    bass_approach=gs.bass_approach,
                    swing_amount=gs.swing_amount,
                    humanize_timing_ms=gs.humanize_timing_ms,
                    humanize_velocity=gs.humanize_velocity,
                    notes=gs.notes,
                ))
                changed = True
            else:
                new_groove_sections.append(gs)

        if not changed:
            return plan

        new_groove = GroovePlan(
            global_feel=plan.groove_plan.global_feel,
            sections=tuple(new_groove_sections),
        )

        return PlanBundle(
            bundle_id=f"plan-{uuid.uuid4().hex[:12]}",
            sketch_id=plan.sketch_id,
            title=plan.title,
            key=plan.key,
            tempo_bpm=plan.tempo_bpm,
            time_signature=plan.time_signature,
            voice_plan=plan.voice_plan,
            form_plan=plan.form_plan,
            harmony_plan=plan.harmony_plan,
            groove_plan=new_groove,
            render_plan=plan.render_plan,
        )
