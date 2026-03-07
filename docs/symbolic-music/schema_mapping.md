# Schema Mapping: Memgraph → Domain → music21

This document maps the three layers of the symbolic-music system:
1. **Memgraph** (graph storage)
2. **Domain** (Python models in `symbolic_music.domain`)
3. **music21** (rendering output)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MEMGRAPH (Storage)                             │
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────────────┐ │
│  │ Identity     │    │ Version Nodes    │    │ Content Nodes              │ │
│  │ Nodes        │    │ (immutable)      │    │ (shared/deduplicated)      │ │
│  │              │    │                  │    │                            │ │
│  │ Composition  │───▶│ CompositionVer   │───▶│ MeterMapVersion            │ │
│  │ Track        │───▶│ TrackVersion     │    │ TempoMapVersion            │ │
│  │ Section      │───▶│ SectionVersion   │───▶│ MeasureVersion             │ │
│  │              │    │                  │    │ EventVersion               │ │
│  │              │    │                  │    │ Pitch                      │ │
│  └──────────────┘    └──────────────────┘    └────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ GraphMusicReader
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DOMAIN (Python)                                │
│                                                                             │
│  CompositionSpec ─┬─▶ MeterMap ──▶ MeterChange ──▶ TimeSignature           │
│                   ├─▶ TempoMap ──▶ TempoChange ──▶ TempoValue              │
│                   └─▶ TrackSpec ─▶ SectionPlacement ──▶ (svid reference)   │
│                                                                             │
│  SectionSpec ────────▶ MeasureSpec ──▶ Events (Note/Rest/Chord/Meta)       │
│                                              │                              │
│                                              └──▶ Pitch, RationalTime       │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ render_composition()
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MUSIC21 (Output)                               │
│                                                                             │
│  Score ──────────────▶ Part ──────────────▶ Measure ──────────────▶ Note   │
│    │                     │                     │                     Chord  │
│    │                     │                     │                     Rest   │
│    ├─▶ Metadata          ├─▶ Instrument        ├─▶ TimeSignature            │
│    └─▶ MetronomeMark     └─▶ Clef              └─▶ (offset positioning)     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Memgraph ERD (Entity-Relationship Diagram)

### Node Types

| Node Label | Primary Key | Purpose |
|------------|-------------|---------|
| `Composition` | `cid` | Identity node - stable handle for a composition |
| `CompositionVersion` | `cvid`, `content_hash` | Immutable snapshot of composition state |
| `Track` | `tid` | Identity node - stable handle for a track |
| `TrackVersion` | `tvid`, `content_hash` | Immutable snapshot of track arrangement |
| `Section` | `sid` | Identity node - stable handle for a section |
| `SectionVersion` | `svid`, `content_hash` | Immutable snapshot of section content |
| `MeasureVersion` | `mvid`, `content_hash` | Immutable measure content |
| `EventVersion` | `evid`, `content_hash` | Immutable event (note/rest/chord/meta) |
| `MeterMapVersion` | `meter_vid`, `content_hash` | Time signature timeline |
| `TempoMapVersion` | `tempo_vid`, `content_hash` | Tempo timeline |
| `Pitch` | `content_hash` | Deduplicated pitch (MIDI + cents) |
| `TimeSignature` | `num`, `den` | Time signature value |
| `TempoValue` | `bpm_n`, `bpm_d`, `beat_unit_den` | Tempo value |
| `Articulation` | `name` | Articulation type |
| `Lyric` | `text` | Lyric text |

### Relationships

```
Composition ─[:LATEST]─────────────────▶ CompositionVersion
CompositionVersion ─[:USES_METERMAP]───▶ MeterMapVersion
CompositionVersion ─[:USES_TEMPOMAP]───▶ TempoMapVersion
CompositionVersion ─[:HAS_TRACK]───────▶ TrackVersion

Track ─[:LATEST]───────────────────────▶ TrackVersion
TrackVersion ─[:USES_SECTION {start_bar, ordinal, repeats, transpose_semitones, role, gain_db}]─▶ SectionVersion

Section ─[:LATEST]─────────────────────▶ SectionVersion
SectionVersion ─[:HAS_MEASURE {i}]─────▶ MeasureVersion

MeasureVersion ─[:HAS_EVENT {i}]───────▶ EventVersion
EventVersion ─[:HAS_PITCH {i}]─────────▶ Pitch
EventVersion ─[:HAS_ARTICULATION {i}]──▶ Articulation
EventVersion ─[:HAS_LYRIC]─────────────▶ Lyric

MeterMapVersion ─[:HAS_CHANGE {at_bar, i}]──▶ TimeSignature
TempoMapVersion ─[:HAS_CHANGE {at_bar, at_beat, i}]──▶ TempoValue
```

---

## Domain Model Hierarchy

```python
CompositionSpec
├── title: str
├── meter_map: MeterMap
│   └── changes: tuple[MeterChange, ...]
│       ├── at_bar: int
│       └── ts: TimeSignature (num, den)
├── tempo_map: TempoMap
│   └── changes: tuple[TempoChange, ...]
│       ├── at_bar: int
│       ├── at_beat: int
│       └── tempo: TempoValue (bpm: RationalTime, beat_unit_den)
└── tracks: tuple[TrackSpec, ...]
    ├── track_id: str
    ├── config: TrackConfig
    │   ├── name: str
    │   ├── instrument_hint: Optional[str]
    │   ├── midi_channel: Optional[int]
    │   ├── clef: Optional[str]
    │   └── transposition_semitones: int
    └── placements: tuple[SectionPlacement, ...]
        ├── section_version_id: str  ◀── references SectionVersion.svid
        ├── start_bar: int
        ├── repeats: int
        ├── transpose_semitones: int
        ├── role: Optional[str]
        └── gain_db: float

SectionSpec  (loaded separately, keyed by svid)
├── name: str
└── measures: tuple[MeasureSpec, ...]
    ├── local_time_signature: Optional[TimeSignature]
    └── events: tuple[AnyEvent, ...]
        │
        ├── NoteEvent
        │   ├── offset_q: RationalTime
        │   ├── dur_q: RationalTime
        │   ├── pitch: Pitch (midi, cents, spelling_hint)
        │   ├── velocity: Optional[int]
        │   ├── tie: Optional[str]
        │   ├── articulations: tuple[str, ...]
        │   └── lyric: Optional[str]
        │
        ├── RestEvent
        │   ├── offset_q: RationalTime
        │   └── dur_q: RationalTime
        │
        ├── ChordEvent
        │   ├── offset_q: RationalTime
        │   ├── dur_q: RationalTime
        │   ├── pitches: tuple[Pitch, ...]
        │   ├── velocity: Optional[int]
        │   ├── tie: Optional[str]
        │   ├── articulations: tuple[str, ...]
        │   └── lyric: Optional[str]
        │
        └── MetaEvent
            ├── offset_q: RationalTime
            ├── dur_q: RationalTime
            ├── meta_type: str
            └── payload: dict
```

---

## Mapping: Domain → music21

| Domain Model | music21 Class | Transformation Notes |
|--------------|---------------|---------------------|
| `CompositionSpec` | `stream.Score` | Title → `score.metadata.title` |
| `TrackSpec` | `stream.Part` | `track_id` → `part.id`, `config.name` → `part.partName` |
| `TrackConfig.instrument_hint` | `instrument.*` | Mapped via `_get_instrument()` lookup table |
| `TrackConfig.clef` | `clef.TrebleClef`, etc. | Direct mapping |
| `SectionSpec` | (expanded into measures) | No direct equivalent - sections are "unrolled" |
| `MeasureSpec` | `stream.Measure` | `local_time_signature` → `meter.TimeSignature` |
| `NoteEvent` | `note.Note` | See detailed mapping below |
| `RestEvent` | `note.Rest` | Duration only |
| `ChordEvent` | `chord.Chord` | Multiple pitches |
| `MetaEvent` | `clef.*`, `dynamics.Dynamic`, `expressions.TextExpression` | Based on `meta_type` |
| `Pitch` | `pitch.Pitch` | `midi` → MIDI number, `spelling_hint` used if valid |
| `RationalTime` | `quarterLength` (float) | `rt.as_float() * 4.0` |
| `MeterMap` | (not directly used) | First time sig applied per section |
| `TempoMap` | `tempo.MetronomeMark` | First tempo inserted at score offset 0 |

### Detailed Event Mapping

```python
# NoteEvent → music21.note.Note
domain_note = NoteEvent(
    offset_q=RationalTime(n=1, d=4),  # → insert at quarterLength 1.0
    dur_q=RationalTime(n=1, d=4),     # → note.quarterLength = 1.0
    pitch=Pitch(midi=60),             # → pitch.Pitch(midi=60)
    velocity=80,                       # → note.volume.velocity = 80
    tie="start",                       # → note.tie = tie.Tie("start")
    articulations=("staccato",),       # → note.articulations.append(Staccato())
    lyric="la",                        # → note.lyric = "la"
)

# ChordEvent → music21.chord.Chord
domain_chord = ChordEvent(
    offset_q=...,
    dur_q=...,
    pitches=(Pitch(midi=60), Pitch(midi=64), Pitch(midi=67)),  # → Chord([p1, p2, p3])
    ...
)

# RestEvent → music21.note.Rest
domain_rest = RestEvent(
    offset_q=...,
    dur_q=RationalTime(n=1, d=2),  # → rest.quarterLength = 2.0
)
```

---

## Data Flow: Graph → Score

```
1. GraphMusicReader.load_composition_by_title("My Song")
   │
   ├─▶ Query: Composition → CompositionVersion (via :LATEST)
   ├─▶ Query: CompositionVersion → MeterMapVersion → MeterChange[]
   ├─▶ Query: CompositionVersion → TempoMapVersion → TempoChange[]
   ├─▶ Query: CompositionVersion → TrackVersion[]
   │       │
   │       └─▶ For each TrackVersion:
   │           ├─▶ Query: TrackVersion → SectionVersion[] (via :USES_SECTION)
   │           │       │
   │           │       └─▶ For each SectionVersion:
   │           │           ├─▶ Query: SectionVersion → MeasureVersion[]
   │           │           │       │
   │           │           │       └─▶ For each MeasureVersion:
   │           │           │           └─▶ Query: MeasureVersion → EventVersion[]
   │           │           │                   │
   │           │           │                   └─▶ For each EventVersion:
   │           │           │                       ├─▶ Query: EventVersion → Pitch[]
   │           │           │                       ├─▶ Query: EventVersion → Articulation[]
   │           │           │                       └─▶ Query: EventVersion → Lyric
   │           │           │
   │           │           └─▶ Build SectionSpec
   │           │
   │           └─▶ Build TrackSpec with SectionPlacements
   │
   └─▶ Return (CompositionSpec, sections_by_svid: dict[str, SectionSpec])

2. render_composition(composition, sections_by_svid)
   │
   ├─▶ Create Score with metadata
   ├─▶ Insert first tempo as MetronomeMark
   │
   └─▶ For each TrackSpec:
       │
       └─▶ render_track(track, sections_by_svid)
           │
           ├─▶ Create Part with id, name, instrument, clef
           │
           └─▶ For each SectionPlacement:
               │
               ├─▶ Lookup section = sections_by_svid[placement.section_version_id]
               ├─▶ Calculate total_transpose = track + placement transposition
               │
               └─▶ For each repeat:
                   │
                   └─▶ render_section(section, start_measure, transpose)
                       │
                       └─▶ For each MeasureSpec:
                           │
                           └─▶ render_measure(measure, measure_number, transpose)
                               │
                               ├─▶ Create Measure
                               ├─▶ Add TimeSignature if first measure
                               │
                               └─▶ For each Event:
                                   │
                                   ├─▶ NoteEvent → render_note_event() → Note
                                   ├─▶ RestEvent → render_rest_event() → Rest
                                   ├─▶ ChordEvent → render_chord_event() → Chord
                                   └─▶ MetaEvent → render_meta_event() → Clef/Dynamic/Text
```

---

## Key Concepts

### 1. Identity vs Version Nodes
- **Identity nodes** (`Composition`, `Track`, `Section`) are stable handles that persist across edits
- **Version nodes** (`CompositionVersion`, etc.) are immutable, content-addressed snapshots
- The `:LATEST` relationship points to the current version

### 2. Content-Addressed Deduplication
- Nodes like `Pitch`, `EventVersion`, `MeasureVersion` use `content_hash` for deduplication
- Same musical content → same node (MERGE on content_hash)

### 3. Section Indirection
- `TrackSpec.placements` contains `section_version_id` references, not embedded sections
- Sections are loaded separately and passed as `sections_by_svid` dict
- This allows section reuse across tracks

### 4. Time Representation
- Domain uses `RationalTime` (exact fractions: `n/d`)
- music21 uses `quarterLength` (float, quarter note = 1.0)
- Conversion: `quarterLength = (n/d) * 4.0`

### 5. Transposition Chain
- `TrackConfig.transposition_semitones` + `SectionPlacement.transpose_semitones`
- Applied during rendering, not stored in events

---

## Quick Reference: Where Things Live

| Concept | Memgraph | Domain | music21 |
|---------|----------|--------|---------|
| Song title | `Composition.title` | `CompositionSpec.title` | `Score.metadata.title` |
| Tempo | `TempoMapVersion` → `TempoValue` | `TempoMap.changes[].tempo` | `MetronomeMark` |
| Time signature | `MeterMapVersion` → `TimeSignature` | `MeterMap.changes[].ts` | `TimeSignature` |
| Instrument | `TrackVersion.instrument_hint` | `TrackConfig.instrument_hint` | `instrument.*` |
| Note pitch | `Pitch.midi` | `Pitch.midi` | `pitch.Pitch.midi` |
| Note duration | `EventVersion.dur_n/dur_d` | `NoteEvent.dur_q` | `Note.quarterLength` |
| Note position | `EventVersion.offset_n/offset_d` | `NoteEvent.offset_q` | `Measure.insert(offset, note)` |
