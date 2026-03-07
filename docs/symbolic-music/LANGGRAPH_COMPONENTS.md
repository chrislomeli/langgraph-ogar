# LangGraph Component Diagram
**Date:** 2026-02-15
**Status:** Design (pre-implementation)

---

## 1. Graph State Schema

The single state object that flows through every node. All nodes read from and write to this.

```python
class MusicGraphState(TypedDict):
    # ── Conversation ──────────────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Intent classification ─────────────────────────────
    intent_type: Literal[
        "new_sketch",       # "Write me a rock tune"
        "plan_refine",      # "Make the chorus busier"
        "ir_refine",        # "Change bar 7 to C minor" (future)
        "load_project",     # "Load bossa rock v2"
        "save_project",     # "Save this as v3"
        "list_projects",    # "What have I saved?"
        "question",         # "What key is the chorus in?"
    ]

    # ── Layer 1: User input ───────────────────────────────
    sketch: Optional[Sketch]

    # ── Seed material (resolved from sketch seeds) ────────
    seed_materials: list[SeedMaterial]     # resolved notes + analysis
    seed_analysis_text: Optional[str]      # human/LLM-readable summary

    # ── Layer 2: AI decisions ─────────────────────────────
    plan: Optional[PlanBundle]
    plan_approved: bool

    # ── Layer 3: Compiled output ──────────────────────────
    compile_result: Optional[CompileResult]

    # ── Layer 4: Rendered output ──────────────────────────
    score_summary: Optional[str]       # text summary for chat
    # (music21 Score is ephemeral, not in persistent state)

    # ── Refinement ────────────────────────────────────────
    refinement_prompt: Optional[str]   # raw user tweak request

    # ── Project management ────────────────────────────────
    project_name: Optional[str]
    project_version: Optional[int]

    # ── Compilation fan-out ───────────────────────────────
    voice_sections: Annotated[list[dict], operator.add]  # fan-in accumulator

    # ── Metadata ──────────────────────────────────────────
    iteration: int                     # how many plan→compile cycles
```

---

## 2. Graph Nodes

### Parent Graph

| Node | Type | Input (reads from state) | Output (writes to state) | LangGraph Feature |
|------|------|--------------------------|--------------------------|-------------------|
| **Intent Router** | LLM | `messages` | `intent_type` | Conditional edges |
| **Creation Subgraph** | Subgraph | (see below) | `sketch`, `plan`, `compile_result`, `score_summary` | Subgraph |
| **Refinement Subgraph** | Subgraph | (see below) | `plan`, `compile_result`, `score_summary` | Subgraph |
| **Load Project** | Tool node | `messages` | `sketch`, `plan`, `compile_result`, `project_name`, `project_version` | Tool binding |
| **Save Project** | Tool node | `plan`, `compile_result`, `project_name` | `project_version` | Tool binding |
| **List Projects** | Tool node | (none) | `messages` (appends AI response) | Tool binding |
| **Answerer** | LLM | `messages`, `plan`, `compile_result` | `messages` (appends answer) | LLM with context |
| **Presenter** | Deterministic | `compile_result`, `score_summary` | `messages` (appends summary) | — |

### Creation Subgraph

| Node | Type | Input | Output | LangGraph Feature |
|------|------|-------|--------|-------------------|
| **Sketch Parser** | LLM | `messages` | `sketch` | Structured output (Pydantic) |
| **Seed Resolver** | Deterministic | `sketch.seed_refs`, `sketch.inline_seeds` | `seed_materials`, `seed_analysis_text` | Tool node |
| **Planner** | LLM or deterministic | `sketch`, `seed_analysis_text` | `plan` | Structured output |
| **Plan Review** | Human checkpoint | `plan` | `plan_approved` or `refinement_prompt` | `interrupt_before` |
| **Voice Compiler (×N)** | Deterministic | `plan`, voice assignment, `seed_materials` | `voice_sections` (one entry) | `Send()` fan-out |
| **Assembler** | Deterministic | `voice_sections` | `compile_result` | Fan-in |
| **Renderer** | Deterministic | `compile_result` | `score_summary` | — |

### Refinement Subgraph

| Node | Type | Input | Output | LangGraph Feature |
|------|------|-------|--------|-------------------|
| **Scope Classifier** | LLM | `messages`, `plan` | `refinement_prompt`, scope info | Conditional edge |
| **Plan Refiner** | LLM or deterministic | `plan`, `refinement_prompt` | `plan` (updated) | — |
| **Plan Review** | Human checkpoint | `plan` | `plan_approved` | `interrupt_before` |
| **Scoped Voice Compiler (×M)** | Deterministic | `plan`, changed voices only | `voice_sections` | `Send()` fan-out (scoped) |
| **Assembler** | Deterministic | `voice_sections`, previous `compile_result` | `compile_result` (merged) | Fan-in + merge |
| **Renderer** | Deterministic | `compile_result` | `score_summary` | — |

---

## 3. Tools

Tools are callable capabilities. Each has typed I/O (Pydantic models).
Invoked by graph nodes — never directly by the user.

### Deterministic Tools (always local)

| Tool | Called by node | Input | Output | Current impl |
|------|---------------|-------|--------|-------------|
| `resolve_seeds` | Seed Resolver | `list[SeedRef]`, `list[InlineSeed]` | `list[SeedMaterial]`, `str` (analysis text) | New: Seed Ingestor pipeline |
| `plan_from_sketch` | Planner | `Sketch`, `seed_analysis_text` | `PlanBundle` | `DeterministicPlanner.plan()` |
| `refine_plan` | Plan Refiner | `PlanBundle`, `str` | `PlanBundle` | `DeterministicPlanner.refine()` |
| `compile_voice` | Voice Compiler | `PlanBundle`, `VoiceSpec`, `CompileOptions`, `list[SeedMaterial]` | `dict[svid, SectionSpec]`, `TrackSpec` | `PatternCompiler` (per-voice) |
| `assemble_composition` | Assembler | `list[TrackSpec]`, `PlanBundle` | `CompileResult` | New: assembles tracks + meter/tempo |
| `render_to_score` | Renderer | `CompileResult` | score summary `str` | `render_composition()` |

### Persistence Tools (local now → MCP later)

| Tool | Called by node | Input | Output | Current impl |
|------|---------------|-------|--------|-------------|
| `save_project` | Save Project | `project_name`, `Sketch`, `PlanBundle`, `CompileResult` | `project_version` | New: Memgraph writer |
| `load_project` | Load Project | `project_name`, `version?` | `Sketch`, `PlanBundle`, `CompileResult` | New: Memgraph reader |
| `list_projects` | List Projects | (none) | `list[ProjectSummary]` | New: Memgraph query |
| `delete_project` | (future) | `project_name`, `version?` | `bool` | Future |

### LLM Tools (structured output)

| Tool | Called by node | Input | Output | Notes |
|------|---------------|-------|--------|-------|
| `parse_sketch` | Sketch Parser | `messages` | `Sketch` | LLM with Pydantic structured output |
| `classify_intent` | Intent Router | `messages`, state summary | `intent_type` | LLM classification |
| `classify_refinement_scope` | Scope Classifier | `messages`, `PlanBundle` | scope + prompt | LLM determines what to change |

---

## 4. Agents (LLM-backed nodes)

| Agent | LLM role | System prompt focus | Tools it can call |
|-------|----------|--------------------|--------------------|
| **Intent Router** | Classifier | "Given the conversation and current state, classify the user's intent" | None (pure classification) |
| **Sketch Parser** | Extractor | "Extract a musical sketch from the user's description" | None (structured output) |
| **Planner** | Creative + structural | "Given this sketch, produce a complete PlanBundle" | `plan_from_sketch` (or direct LLM output) |
| **Scope Classifier** | Analyzer | "What part of the plan does the user want to change?" | None (classification) |
| **Plan Refiner** | Editor | "Apply this refinement to the existing plan" | `refine_plan` (or direct LLM output) |
| **Answerer** | Q&A | "Answer questions about the current sketch/plan/composition" | None (reads state) |

---

## 5. Conditional Edges

### Parent Graph: after Intent Router

```
intent_type == "new_sketch"   → Creation Subgraph
intent_type == "plan_refine"  → Refinement Subgraph
intent_type == "ir_refine"    → Refinement Subgraph (IR path, future)
intent_type == "load_project" → Load Project → Presenter
intent_type == "save_project" → Save Project → Presenter
intent_type == "list_projects"→ List Projects → Presenter
intent_type == "question"     → Answerer
```

### Creation Subgraph: after Plan Review

```
plan_approved == True   → Voice Compiler fan-out
plan_approved == False  → Planner (with feedback in messages)
```

### Refinement Subgraph: after Plan Review

```
plan_approved == True   → Scoped Voice Compiler fan-out
plan_approved == False  → Plan Refiner (with feedback)
```

---

## 6. LangGraph Features Used

| Feature | Where | Portfolio value |
|---------|-------|----------------|
| **Subgraphs** | Creation, Refinement | Modular multi-phase agent design |
| **Human-in-the-loop (`interrupt`)** | Plan Review | Collaborative AI with user agency |
| **Checkpointing** | All state (SQLite local, Postgres deploy) | Multi-session resumability |
| **Dynamic fan-out (`Send`)** | Voice compilation | Parallel task execution |
| **Fan-in** | Assembler | Aggregation of parallel results |
| **Conditional edges** | Intent Router, Plan Review | State-aware routing |
| **Structured output** | Sketch Parser, Planner | Type-safe LLM ↔ code boundary |
| **Tool nodes** | Save/Load/Render | Clean tool abstraction (→ MCP) |

---

## 7. Component Inventory Summary

```
AGENTS (LLM-backed):     5  (Router, Sketch Parser, Planner, Scope Classifier, Answerer)
GRAPH NODES:             15  (7 parent + 7 creation + 6 refinement, some shared)
TOOLS (deterministic):    6  (resolve_seeds, plan, refine, compile_voice, assemble, render)
TOOLS (persistence):      3  (save, load, list)
TOOLS (LLM):              3  (parse_sketch, classify_intent, classify_scope)
SUBGRAPHS:                2  (Creation, Refinement)
STATE FIELDS:            14
CONDITIONAL EDGES:        4  (intent routing, plan review ×2, scope routing)
```

---

## 8. Data Flow Summary

```
User message
  │
  ▼
Intent Router ─── classifies ──→ intent_type
  │
  ├─ new_sketch ──→ Sketch Parser ──→ Seed Resolver ──→ Planner ──→ Plan Review (INTERRUPT)
  │                                                    │
  │                                              approve / reject+feedback
  │                                                    │
  │                                              Voice Compiler ×N (SEND fan-out)
  │                                                    │
  │                                              Assembler (fan-in)
  │                                                    │
  │                                              Renderer ──→ Presenter
  │
  ├─ plan_refine ──→ Scope Classifier ──→ Plan Refiner ──→ Plan Review (INTERRUPT)
  │                                                            │
  │                                                      (same compile path, scoped)
  │
  ├─ load_project ──→ Load (hydrate state) ──→ Presenter
  │
  ├─ save_project ──→ Save (persist all) ──→ Presenter
  │
  ├─ list_projects ──→ List ──→ Presenter
  │
  └─ question ──→ Answerer
```
