# LangGraph Use Cases
**Date:** 2026-02-15
**Purpose:** Validate the component diagram against real scenarios before implementing.

Each use case traces the exact path through the graph, listing:
- User message(s)
- Nodes visited (in order)
- State mutations at each step
- Tools called
- LangGraph features exercised

---

## Use Case 1: New Composition (Happy Path)

**Scenario:** User starts fresh, creates a rock tune, approves the plan, gets playback.

```
User: "Write me a rock tune in A minor with a bossa groove, verse-chorus-bridge form"
```

### Trace

| Step | Node | Action | State change | Tool / Feature |
|------|------|--------|-------------|----------------|
| 1 | **Intent Router** | LLM classifies message | `intent_type = "new_sketch"` | Conditional edge |
| 2 | → **Creation Subgraph** | Enters subgraph | — | Subgraph |
| 3 | **Sketch Parser** | LLM extracts structured sketch | `sketch = Sketch(prompt="rock tune...", key="A minor", ...)` | Structured output |
| 4 | **Planner** | Produces plan from sketch | `plan = PlanBundle(...)` with 4 voices, 7 sections | Tool: `plan_from_sketch` |
| 5 | **Plan Review** | Graph pauses, presents plan summary to user | — | `interrupt_before` |

```
System: "Here's the plan:
  Title: Rock Tune in A Minor
  Key: A minor | Tempo: 120 BPM | Time: 4/4
  Voices: Drums, Bass, Rhythm Guitar, Piano
  Form: intro(4) → verse1(8) → chorus1(8) → verse2(8) → chorus2(8) → bridge(8) → chorus3(8) → outro(4)
  
  Approve, or tell me what to change?"
```

```
User: "Looks good, go ahead"
```

| Step | Node | Action | State change | Tool / Feature |
|------|------|--------|-------------|----------------|
| 6 | **Plan Review** resumes | User approved | `plan_approved = True` | Interrupt resume |
| 7 | **Voice Compiler ×4** | Fan-out: drums, bass, guitar, piano compiled in parallel | `voice_sections += [...]` (4 entries) | `Send()` fan-out |
| 8 | **Assembler** | Merges voice results into CompositionSpec | `compile_result = CompileResult(...)` | Fan-in |
| 9 | **Renderer** | Produces music21 Score, generates summary | `score_summary = "4 parts, 56 bars, 847 notes"` | Tool: `render_to_score` |
| 10 | **Presenter** | Shows summary to user | Appends message to `messages` | — |

```
System: "Composition ready:
  4 parts, 56 bars, 847 notes
  [Play] [Export MIDI] [Export MusicXML]
  
  Want to refine anything, or save?"
```

### Features exercised:
Subgraph, structured output, interrupt, fan-out/fan-in, conditional edges

---

## Use Case 2: Plan Rejection + Feedback Loop

**Scenario:** User doesn't like the plan, gives feedback, planner revises.

```
User: "Write me a jazz ballad"
```

| Step | Node | State change |
|------|------|-------------|
| 1 | Intent Router | `intent_type = "new_sketch"` |
| 2 | Sketch Parser | `sketch = Sketch(prompt="jazz ballad")` |
| 3 | Planner | `plan = PlanBundle(...)` with sax, piano, bass, drums |
| 4 | Plan Review | (interrupt — presents plan) |

```
System: "Plan: Jazz Ballad, Bb major, 72 BPM
  Voices: Drums, Bass, Piano, Tenor Sax
  Form: intro → verse1 → chorus1 → verse2 → chorus2 → bridge → chorus3 → outro
  
  Approve, or tell me what to change?"
```

```
User: "Drop the sax, add a trumpet. And make it AABA form."
```

| Step | Node | State change |
|------|------|-------------|
| 5 | Plan Review resumes | `plan_approved = False`, feedback in `messages` |
| 6 | → **Planner** (loop back) | Planner sees feedback, revises plan | 
| 7 | | `plan = PlanBundle(...)` — trumpet replaces sax, AABA form |
| 8 | Plan Review | (interrupt again — presents revised plan) |

```
System: "Revised plan:
  Voices: Drums, Bass, Piano, Trumpet
  Form: A1(8) → A2(8) → B(8) → A3(8)
  
  Approve?"
```

```
User: "Perfect"
```

| Step | Node | State change |
|------|------|-------------|
| 9 | Plan Review resumes | `plan_approved = True` |
| 10-13 | Voice Compiler → Assembler → Renderer → Presenter | (same as UC1) |

### Features exercised:
Interrupt with rejection, conditional edge looping back to Planner, state accumulation across iterations

### Design question surfaced:
> When the user rejects and gives feedback, does the **Planner** re-run from the Sketch + feedback, or does the **Plan Refiner** apply a delta to the existing plan?

**Answer:** Route to the **Planner** (not Refiner) because the user is changing fundamental structure (form, voice roster). The Refiner handles incremental tweaks to an approved plan. The Plan Review node's conditional edge should distinguish:
- Feedback that changes structure → back to Planner
- Minor tweaks → Plan Refiner

For v1 implementation: always route back to Planner on rejection. Optimize later.

---

## Use Case 3: Post-Compilation Refinement

**Scenario:** User has a composition, listens, wants to change the groove.

Starting state: `plan` and `compile_result` are populated from a previous run.

```
User: "Make the chorus drums busier and add a latin percussion track"
```

| Step | Node | State change |
|------|------|-------------|
| 1 | Intent Router | `intent_type = "plan_refine"` |
| 2 | → **Refinement Subgraph** | Enters subgraph |
| 3 | **Scope Classifier** | LLM determines: groove change (drums density) + voice change (add percussion) | 
| 4 | | `refinement_prompt = "Make chorus drums busier, add latin percussion"` |
| 5 | **Plan Refiner** | Applies refinements to existing plan |
| 6 | | `plan = PlanBundle(...)` — chorus drum density → busy, new percussion voice added |
| 7 | **Plan Review** | (interrupt — shows diff) |

```
System: "Refined plan:
  CHANGED: Chorus drum density: medium → busy
  ADDED: Latin Percussion (congas, sparse density)
  
  Approve?"
```

```
User: "Yes"
```

| Step | Node | State change |
|------|------|-------------|
| 8 | Plan Review resumes | `plan_approved = True` |
| 9 | **Scoped Voice Compiler ×2** | Fan-out: only drums + new percussion | `voice_sections += [...]` |
| 10 | **Assembler** | Merges with previous compile_result (preserves bass, guitar, piano) | `compile_result = CompileResult(...)` |
| 11 | Renderer → Presenter | Updated summary |

### Features exercised:
Refinement subgraph, scoped fan-out (only changed voices), merge with previous result

### Design question surfaced:
> How does the Assembler know which voices to preserve from the previous result?

**Answer:** `CompileOptions.regenerate_voices` already supports this. The Refinement Subgraph sets this based on the Scope Classifier's output. The Assembler receives the previous `compile_result` and the new voice sections, and merges them.

---

## Use Case 4: Save and Load Across Sessions

**Scenario:** User saves work, comes back later, loads it, and continues refining.

### Session 1: Save

Starting state: `plan` and `compile_result` populated.

```
User: "Save this as Bossa Rock Demo"
```

| Step | Node | State change |
|------|------|-------------|
| 1 | Intent Router | `intent_type = "save_project"` |
| 2 | **Save Project** | Persists Sketch + PlanBundle + CompileResult to Memgraph |
| 3 | | `project_name = "Bossa Rock Demo"`, `project_version = 1` |
| 4 | Presenter | "Saved Bossa Rock Demo v1" |

### Session 2: Load + Refine

New graph invocation, empty state.

```
User: "Load Bossa Rock Demo"
```

| Step | Node | State change |
|------|------|-------------|
| 1 | Intent Router | `intent_type = "load_project"` |
| 2 | **Load Project** | Reads from Memgraph, hydrates state |
| 3 | | `sketch = ...`, `plan = ...`, `compile_result = ...`, `project_name = "Bossa Rock Demo"`, `project_version = 1` |
| 4 | Presenter | Shows plan summary + composition summary |

```
System: "Loaded Bossa Rock Demo v1:
  A minor, 120 BPM, 6 voices, 48 bars
  What would you like to change?"
```

```
User: "Add a guitar solo section after the bridge"
```

| Step | Node | State change |
|------|------|-------------|
| 5 | Intent Router | `intent_type = "plan_refine"` |
| 6-12 | (Refinement Subgraph — same as UC3) | Plan updated, recompiled, rendered |

```
User: "Save this"
```

| Step | Node | State change |
|------|------|-------------|
| 13 | Intent Router | `intent_type = "save_project"` |
| 14 | Save Project | `project_version = 2` |
| 15 | Presenter | "Saved Bossa Rock Demo v2" |

### Features exercised:
Checkpointing (implicit), persistence tools, state hydration, multi-session continuity

### Design question surfaced:
> Should "Save" use LangGraph checkpointing or custom Memgraph persistence?

**Answer:** Both, for different purposes:
- **LangGraph checkpointer** saves *conversation state* (messages, in-flight decisions). This is for resuming mid-conversation (e.g., browser refresh).
- **Memgraph persistence** saves *musical artifacts* (Sketch, PlanBundle, CompositionSpec). This is for named projects with versions.

They serve different needs. The checkpointer is automatic and ephemeral. Memgraph persistence is explicit and permanent.

---

## Use Case 5: Question About Current State

**Scenario:** User wants to understand the current composition without changing anything.

Starting state: `plan` and `compile_result` populated.

```
User: "What key is the bridge in? And how many bars is the whole piece?"
```

| Step | Node | State change |
|------|------|-------------|
| 1 | Intent Router | `intent_type = "question"` |
| 2 | **Answerer** | LLM reads `plan` and `compile_result` from state, answers |
| 3 | | Appends answer to `messages` |

```
System: "The bridge is in A minor (same as the global key).
  The whole piece is 48 bars across 7 sections."
```

No state mutation. No tools called. Just LLM reading state and answering.

### Features exercised:
State-aware LLM, conditional routing to a non-mutating path

---

## Use Case 6: List Projects

**Scenario:** User wants to see what they've saved.

```
User: "What projects do I have?"
```

| Step | Node | State change |
|------|------|-------------|
| 1 | Intent Router | `intent_type = "list_projects"` |
| 2 | **List Projects** | Queries Memgraph for all project identity nodes |
| 3 | Presenter | Formats and shows list |

```
System: "Your projects:
  1. Bossa Rock Demo (v1, v2) — A minor, 120 BPM, 6 voices
  2. Jazz Ballad (v1) — Bb major, 72 BPM, 4 voices"
```

### Features exercised:
Persistence tool, simple routing

---

## Use Case 7: Composition from a Melodic Seed

**Scenario:** User provides a MIDI melody and asks the system to build a full arrangement around it.

```
User: "Here's a melody I wrote [attaches melody.mid]. Build a jazz arrangement around it."
```

### Trace

| Step | Node | Action | State change |
|------|------|--------|-------------|
| 1 | **Intent Router** | Classifies as new composition with seed | `intent_type = "new_sketch"` |
| 2 | → **Creation Subgraph** | | |
| 3 | **Sketch Parser** | LLM extracts sketch, notes the MIDI attachment | `sketch = Sketch(prompt="jazz arrangement", inline_seeds=[...])` |
| 4 | **Seed Resolver** | Parses MIDI → NoteEvents, extracts features | `seed_materials = [SeedMaterial(notes=[...], analysis=...)]` |
| | | | `seed_analysis_text = "Seed Analysis:\n  Key fit: Bb major (90%)..."` |

The `seed_analysis_text` produced by the resolver looks like:

```
Seed Analysis:
  Source: melody.mid (8 bars, single voice)
  Key fit: Bb major (90%), Bb mixolydian (75%)
  Contour: ascending bars 1-4, descending bars 5-8 (arch)
  Range: Bb3 to F5 (octave + fifth)
  Rhythm: mostly eighth notes, syncopation on beats 2 and 4
  Intervals: stepwise (55%), minor thirds (30%), fifths (15%)
  Phrase length: 4 bars (two phrases, call-response pattern)
  Density: medium (6-8 notes per bar)
  Style cues: mixolydian vocabulary, swing-friendly rhythm → jazz/blues feel
```

| Step | Node | Action | State change |
|------|------|--------|-------------|
| 5 | **Planner** | LLM reads sketch + seed_analysis_text | `plan = PlanBundle(...)` |
| | | Infers: Bb major, swing feel, walking bass, | Key/harmony compatible with seed |
| | | piano comping, brush drums | Voice roster complements seed |
| | | Seed voice assigned to "lead" (sax or melody) | Seed NoteEvents used verbatim |
| 6 | **Plan Review** | (interrupt — shows plan + seed analysis) | |

```
System: "Plan based on your melody:
  Seed analysis: Bb major, arch contour, swing-friendly, jazz/blues feel
  
  Key: Bb major | Tempo: 140 BPM | Feel: swing
  Voices: Lead (your melody), Piano, Walking Bass, Brush Drums
  Form: intro(4) → A1(8) → A2(8) → B(8) → A3(8) → outro(4)
  Harmony: I-vi-ii-V progression, compatible with your melody's Bb major tonality
  
  Approve?"
```

```
User: "Add a tenor sax solo section"
```

| Step | Node | Action | State change |
|------|------|--------|-------------|
| 7 | Plan Review resumes | `plan_approved = False`, feedback in messages | |
| 8 | → **Planner** (loop) | Adds solo section, tenor sax voice | `plan` updated |
| 9 | Plan Review | (interrupt again) | |

```
User: "Perfect"
```

| Step | Node | Action | State change |
|------|------|--------|-------------|
| 10 | Plan Review resumes | `plan_approved = True` | |
| 11 | **Voice Compiler ×5** | Fan-out: lead uses seed NoteEvents directly; others generated | `voice_sections += [...]` |
| | | Lead voice: seed notes transposed/placed per form | |
| | | Other voices: generated to complement seed | |
| 12 | **Assembler** → **Renderer** → **Presenter** | (standard path) | |

### How the compiler uses seed material:

- **Lead voice**: Seed `NoteEvent`s are placed verbatim (or transposed to match section key) into the lead track's sections. The seed *is* the content for that voice.
- **Harmony voices** (piano, bass): Generated from `HarmonyPlan`, which was informed by the seed's key/scale analysis.
- **Rhythm voices** (drums): Generated from `GroovePlan`, which was informed by the seed's rhythmic density and style cues.

### Features exercised:
Seed Resolution pipeline, LLM reading extracted features, seed-aware compilation, full creation flow

### Design questions surfaced:
> How does the compiler know which voice gets the seed?

**Answer:** The Planner assigns a `seed_voice_id` in the `VoicePlan` — one voice is tagged as the seed carrier. The compiler checks this and uses seed `NoteEvent`s instead of generating patterns.

> What if the seed is longer/shorter than the section?

**Answer:** The compiler truncates or loops the seed to fit the section's bar count. Transposition is applied if the section's key differs from the seed's detected key.

---

## Use Case 8: Demucs Pipeline (Aspirational)

**Scenario:** User provides a full song audio file. System separates stems, extracts MIDI, and uses the bass line as a seed.

```
User: "Here's a song I like [attaches song.mp3]. Use the bass line as a seed for a new rock arrangement."
```

### Trace (aspirational — not MVP)

| Step | Node | Action |
|------|------|--------|
| 1 | Intent Router | `intent_type = "new_sketch"` |
| 2 | Sketch Parser | `sketch = Sketch(prompt="rock arrangement", seed_refs=[SeedRef(kind="audio_stem", ref="song.mp3:bass")])` |
| 3 | **Seed Resolver** | Dispatches to Demucs ingestor: |
| | | 1. `demucs song.mp3` → `bass.wav`, `drums.wav`, `vocals.wav`, `other.wav` |
| | | 2. `basic-pitch bass.wav` → `bass.mid` |
| | | 3. Parse `bass.mid` → `list[NoteEvent]` |
| | | 4. Extract features → `SeedAnalysis` |
| | | Result: `seed_materials`, `seed_analysis_text` |
| 4 | Planner | LLM reads seed analysis, builds plan around the bass line |
| 5+ | (same as UC7 from here) | |

### Why this works architecturally:

The Seed Resolver has a pluggable ingestor interface:

```
SeedIngestor (ABC)
  ├── InlineSeedIngestor      ← MVP: parse InlineSeed from Sketch
  ├── MidiFileIngestor        ← MVP: parse .mid files
  ├── GraphSeedIngestor       ← MVP: resolve SeedRef from Memgraph
  └── DemucsIngestor          ← Future: audio → stems → MIDI → ingest
```

All produce the same output: `SeedMaterial` (resolved notes + `SeedAnalysis`).
The Planner and Compiler never know where the seed came from.

### Not MVP because:
- Demucs requires a GPU or significant CPU time
- Audio-to-MIDI (basic-pitch, omnizart) is imperfect
- Adds external dependencies (demucs, basic-pitch)

But the architecture is ready — adding `DemucsIngestor` is a single new class implementing the existing interface.

---

## Summary: Gaps and Decisions Surfaced

| # | Question | Proposed answer |
|---|----------|----------------|
| 1 | Plan rejection: Planner or Refiner? | Planner for structural changes, Refiner for tweaks. V1: always Planner on rejection. |
| 2 | How does Assembler merge scoped results? | Uses `CompileOptions.regenerate_voices` + previous `CompileResult`. Already designed. |
| 3 | Checkpointer vs Memgraph persistence? | Both. Checkpointer = conversation state (automatic). Memgraph = musical artifacts (explicit save). |
| 4 | What does Plan Review show the user? | Structured summary: voices, form, harmony overview, groove feel. Diff view for refinements. |
| 5 | Can the user skip Plan Review? | Yes — add a "fast mode" flag. But default is always review. Good for demo. |
| 6 | What if state is empty and user says "make it busier"? | Intent Router detects no plan in state → asks user to create or load first. |
| 7 | How does the compiler know which voice gets the seed? | Planner assigns `seed_voice_id` in VoicePlan. Compiler uses seed NoteEvents for that voice. |
| 8 | What if seed is longer/shorter than section? | Compiler truncates or loops. Transposition applied if section key differs from seed key. |
| 9 | Where does seed analysis text go? | Into graph state as `seed_analysis_text`. Planner LLM reads it. Also shown in Plan Review. |
| 10 | Is the Seed Resolver always called? | Only if `sketch.seed_refs` or `sketch.inline_seeds` are non-empty. Otherwise skipped (no-op). |
