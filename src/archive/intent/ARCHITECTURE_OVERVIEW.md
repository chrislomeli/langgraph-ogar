# Symbolic Music Generation Architecture
**Date:** 2026-02-14
**Status:** Implemented (Phase 1)
**Goal:** Architecture-first system that turns conversational musical sketches into versioned, storable symbolic compositions, supporting iterative refinement and audition via renderers (music21, MIDI).

---

## Core Principle: Separate **storable** from **playable**
- **Storable truth:** Composition IR (domain models persisted in Memgraph via `GraphMusicWriter`).
- **Playable views:** Projections/renderers (IR → music21 → playback/export; IR → MIDI 1.x; future: MIDI 2.0 UMP).

music21 objects are procedural runtime artifacts, never canonical state.

---

## Layers and Artifacts

### Layer 1 — Sketch (user input)
**What the user wants**, expressed naturally.

**Artifact:** `Sketch` (`sketch_models.py`)
- Free-text prompt: genre, mood, style, structure, energy
- Optional structured hints: key, tempo, time signature, form
- Voice hints with importance levels (required / preferred / optional)
- Exclusions (instruments, styles, techniques to avoid)
- Seed material: references to graph objects (`SeedRef`) or inline note data (`InlineSeed`)

**Key design decision:** The Sketch is deliberately loose — mostly strings and optionals. The user should not need to make planning-level decisions. An LLM (or the deterministic planner) interprets the sketch into a precise plan.

### Layer 2 — Plan (AI output)
**Concrete decisions** that bridge sketch → notes. Fully resolved, enum-heavy, compiler-ready.

**Artifact:** `PlanBundle` (`plan_models.py`)
- `VoicePlan`: DAW-stable track roster with stable `voice_id`s, roles, instruments, section participation masks. Lockable.
- `FormPlan`: Section definitions (`SectionPlan`) + timeline placements. Each section has role, bar count, energy, density.
- `HarmonyPlan`: Per-section chord progressions with root, quality, bar/beat positions.
- `GroovePlan`: Per-section feel, drum/perc density, bass approach, swing amount, humanization targets.
- `RenderPlan`: Export targets and preferences.

**Key design decision:** The plan is the checkpoint. The user reviews it, optionally tweaks it, then locks it. The compiler reads it deterministically.

### Layer 3 — Composition IR (existing, canonical)
**What is generated:** Domain model objects persisted in Memgraph.
- `CompositionSpec`, `TrackSpec`, `SectionSpec`, `MeasureSpec`
- `NoteEvent`, `RestEvent`, `ChordEvent`, `MetaEvent`
- `MeterMap`, `TempoMap`, `TimeSignature`, `TempoValue`
- `Pitch`, `RationalTime`

### Layer 4 — Renderers (existing tools + future)
- IR → music21 Score (audition, analysis, MusicXML export)
- IR → MIDI 1.x SMF (DAW import)
- Future: IR → MIDI 2.0 UMP / streaming interface

---

## End-to-End Pipeline

```
User prompt ──► Sketch ──► Planner ──► PlanBundle ──► Compiler ──► CompileResult
                                          │                            │
                                     user review                  CompositionSpec
                                     & lock                       + SectionSpecs
                                          │                            │
                                     refinement?               ┌──────┴──────┐
                                     (plan-level)              │             │
                                          │                 Persist      Render
                                     new PlanBundle        (Memgraph)   (music21/MIDI)
                                     → recompile
```

### Implemented Flow

1. **Sketch** — User provides free-text prompt + optional hints/seeds.
   - `Sketch` model in `sketch_models.py`

2. **Planner** — Interprets sketch into a fully-resolved `PlanBundle`.
   - `DeterministicPlanner` in `planner.py` (rule-based, first implementation)
   - Parses genre, feel, key, tempo, form from prompt keywords
   - Builds voice roster from genre profiles + user hints
   - Generates harmony progressions from scale-degree templates
   - Sets groove parameters per section based on energy/feel
   - Future: LLM-backed planner (same interface, richer interpretation)

3. **Compiler** — Transforms `PlanBundle` into domain IR.
   - `PatternCompiler` in `compiler.py` (implements `PlanCompiler` ABC)
   - Per-voice generators: drums, bass, keys, guitar, pad, percussion
   - Patterns driven by `HarmonyPlan` (chord roots/qualities) and `GroovePlan` (feel, density, bass approach)
   - Produces `CompileResult`: `CompositionSpec` + `dict[svid, SectionSpec]`
   - Supports scoped regeneration via `CompileOptions`

4. **Persist** — Commit to Memgraph with lineage edges.
   - Existing `GraphMusicWriter` handles IR persistence
   - Lineage: `Sketch → PlanBundle → CompositionVersion`

5. **Render** — IR → music21 Score → playback/export.
   - Existing `render_composition()` in `rendering/music21.py`

---

## Refinement Protocol

Two kinds of tweaks, handled at different layers:

### Plan-Level Refinements
- **What:** "Add a bridge", "Drop the strings", "Make the chorus busier"
- **Mechanism:** `RefinementRequest` → planner produces new `PlanBundle` → recompile
- **Scope:** `RefinementScope` enum targets specific sub-plans (voice, form, harmony, groove)
- **Implemented:** `DeterministicPlanner.refine()` handles add/remove sections, density adjustments

### IR-Level Refinements (stubbed)
- **What:** "Change bar 7 to C minor", "Add a fill in bar 16"
- **Mechanism:** `IRRefinementRequest` → `IREditor.apply()` → surgical edits to `CompileResult`
- **Contract:** `IREditor` ABC in `compiler_interface.py`
- **Status:** Interface defined, implementation deferred

---

## Scoped Regeneration

Each compilation supports selective regeneration:
- `CompileOptions.regenerate_voices`: Only regenerate specific voice_ids; preserve others from previous `CompileResult`
- `CompileOptions.regenerate_sections`: Only regenerate specific section_ids
- `CompileOptions.seed`: Deterministic random seed for reproducibility
- Previous `CompileResult` passed to `compile()` for preservation

This enables: "Regenerate only the drums" or "Redo the chorus harmony" without touching anything else.

---

## Data Lineage in Memgraph

Three first-class versioned artifacts:
- `Sketch` (user input, versioned)
- `PlanBundle` (AI decisions, versioned)
- `Composition` (canonical IR, versioned via existing identity/version node pattern)

Edges:
- `(:Sketch)-[:PLANNED_AS]->(:PlanBundle)`
- `(:PlanBundle)-[:COMPILED_TO]->(:CompositionVersion)`
- `(:CompositionVersion)-[:RENDERED_AS]->(:Artifact {type:"midi1"|"music21"})`
- `(:PlanBundle)-[:REFINED_FROM]->(:PlanBundle)` (refinement chain)

---

## Implementation Boundaries

| Module | Responsibility |
|--------|---------------|
| `sketch_models.py` | User-facing input: `Sketch`, `VoiceHint`, `SeedRef`, `InlineSeed` |
| `plan_models.py` | AI-facing output: `PlanBundle`, all sub-plans, `RefinementRequest`, `IRRefinementRequest` |
| `planner.py` | `DeterministicPlanner`: Sketch → PlanBundle (+ plan-level refinements) |
| `compiler_interface.py` | ABCs: `PlanCompiler`, `IREditor`; dataclasses: `CompileResult`, `CompileOptions` |
| `compiler.py` | `PatternCompiler`: PlanBundle → CompileResult (per-voice pattern generators) |
| Existing `symbolic_music.domain` | Immutable domain models (IR) |
| Existing `symbolic_music.persistence` | Memgraph read/write with content-addressed versioning |
| Existing `symbolic_music.rendering` | IR → music21 Score |

---

## MIDI 2.0 Positioning
MIDI (1.x or 2.0) is a **renderer backend**:
- Canonical meaning lives in Sketch / Plan / IR.
- MIDI 2.0 adds expressive per-note controls; implement as an additional renderer without changing planning or compilation contracts.

---

## What "Done" Looks Like

### Phase 1 (implemented)
- Sketch → PlanBundle → CompileResult → music21 Score
- Deterministic planner with genre profiles
- Pattern-based compiler with per-voice generators
- Plan-level refinements (add/remove sections, adjust density)
- Scoped regeneration
- Full pipeline demo

### Phase 2 (next)
- LLM-backed planner (LangGraph agent)
- Richer pattern generators (melodic contour, rhythmic variation)
- IR-level refinement implementation
- Memgraph lineage persistence for Sketch and PlanBundle
- MIDI 1.x export renderer

### Phase 3 (future)
- LLM-assisted compilation (hybrid: patterns + LLM for melodic invention)
- User collaboration loop in LangGraph (propose → review → lock → compile → audition → refine)
- MIDI 2.0 renderer
- Seed material resolution from graph (use existing sections as starting points)
