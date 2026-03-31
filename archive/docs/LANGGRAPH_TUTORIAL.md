# LangGraph Tutorial: Building a Symbolic Music Agent
**Date:** 2026-02-15
**Audience:** You, learning LangGraph by building your real project
**Prerequisites:** Python, Pydantic, the existing intent layer (Sketch, PlanBundle, PatternCompiler)

---

## Project Folder Organization

Here's the full project structure. **Existing files** are what you've already built. **New files** are what the tutorial creates, tagged with the milestone that introduces them.

```
symbolic-music/
│
├── pyproject.toml
├── docker-compose.yml                  # Memgraph
├── environment.yml
│
├── docs/
│   ├── LANGGRAPH_COMPONENTS.md         # Component diagram (reference)
│   ├── LANGGRAPH_USE_CASES.md          # Use case traces (reference)
│   ├── LANGGRAPH_TUTORIAL.md           # This file
│   ├── persistence_data_layer.md       # Existing: Memgraph schema docs
│   └── schema_mapping.md              # Existing: domain ↔ graph mapping
│
├── src/
│   │
│   ├── symbolic_music/                 # ── EXISTING: Domain layer ──────────
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── models.py              # CompositionSpec, TrackSpec, SectionSpec, NoteEvent, etc.
│   │   │   └── errors.py
│   │   ├── persistence/
│   │   │   ├── __init__.py
│   │   │   ├── adapter.py             # Memgraph adapter
│   │   │   ├── reader.py              # Sync reader
│   │   │   ├── writer.py              # Sync writer
│   │   │   ├── async_reader.py        # Async reader
│   │   │   ├── async_writer.py        # Async writer
│   │   │   ├── types.py               # Persistence types
│   │   │   └── schema/                # Cypher schema scripts
│   │   └── rendering/
│   │       ├── __init__.py
│   │       └── music21.py             # render_composition() → music21 Score
│   │
│   ├── intent/                         # ── EXISTING: Intent layer ──────────
│   │   ├── __init__.py                # Barrel exports
│   │   ├── sketch_models.py           # Sketch, SeedRef, InlineSeed, VoiceHint
│   │   ├── plan_models.py            # PlanBundle, VoicePlan, FormPlan, HarmonyPlan, etc.
│   │   ├── planner.py                # DeterministicPlanner (Sketch → PlanBundle)
│   │   ├── compiler_interface.py     # ABCs: PlanCompiler, IREditor, CompileResult
│   │   ├── compiler.py               # PatternCompiler (PlanBundle → CompileResult)
│   │   ├── ARCHITECTURE_OVERVIEW.md
│   │   └── intent_models_SUPERSEDED.py  # Old models (kept for reference)
│   │
│   ├── tools/                          # ── NEW: Centralized tool definitions ─
│   │   ├── __init__.py                # Package docstring                    (pre-M1)
│   │   ├── project_tools.py           # Project planner LangGraph tools      (pre-M1)
│   │   ├── intent_tools.py            # Sketch → Plan → Compile tools        (M6)
│   │   ├── music_tools.py             # Rendering & domain tools             (M6)
│   │   └── persistence_tools.py       # Save/load/list composition tools     (M7)
│   │
│   ├── graph/                          # ── NEW: LangGraph layer ────────────
│   │   ├── __init__.py                # Top-level barrel exports
│   │   │
│   │   ├── m1/                        # ── Milestone 1: Basic graph ─────────
│   │   │   ├── __init__.py            # Barrel exports
│   │   │   ├── state.py               # MusicGraphState TypedDict
│   │   │   ├── graph_builder.py       # Linear graph: START → process → presenter → END
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       └── presenter.py       # Format results for user
│   │   │
│   │   ├── m2/                        # ── Milestone 2: Router ──────────────
│   │   │   ├── __init__.py
│   │   │   ├── state.py               # + IntentType enum
│   │   │   ├── graph_builder.py       # Conditional edges, intent routing
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       ├── intent_router.py   # Classify user intent → route
│   │   │       └── stub_nodes.py      # Stub destinations for each intent
│   │   │
│   │   ├── m3/                        # ── Milestone 3: Human-in-the-loop ───
│   │   │   ├── __init__.py
│   │   │   ├── state.py               # + plan, approved, compiled fields
│   │   │   ├── graph_builder.py       # MemorySaver, interrupt(), approve/reject cycle
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       ├── mock_planner.py    # Fake plan for testing
│   │   │       └── plan_review.py     # interrupt() — pause, receive human decision
│   │   │
│   │   ├── m4/                        # ── Milestone 4: Fan-out / Fan-in ────
│   │   │   ├── __init__.py
│   │   │   ├── state.py               # + voice_sections (Annotated reducer)
│   │   │   ├── graph_builder.py       # Send(), parallel voice compilation
│   │   │   └── nodes/
│   │   │       ├── __init__.py
│   │   │       ├── compile_voice.py   # Compile single voice (fan-out)
│   │   │       └── assembler.py       # Merge voice results (fan-in)
│   │   │
│   │   ├── m5/                        # ── Milestone 5: Subgraphs ───────────
│   │   │   ├── __init__.py
│   │   │   ├── state.py
│   │   │   ├── graph_builder.py       # Parent graph with nested subgraph
│   │   │   └── subgraphs/
│   │   │       ├── __init__.py
│   │   │       └── creation.py        # Sketch → Plan → Compile → Render
│   │   │
│   │   ├── m6/                        # ── Milestone 6: Real tools ──────────
│   │   │   └── ...                    # Wire DeterministicPlanner, PatternCompiler, LLM nodes
│   │   │
│   │   ├── m7/                        # ── Milestone 7: Persistence ─────────
│   │   │   └── ...                    # SqliteSaver, Memgraph save/load/list
│   │   │
│   │   └── m8/                        # ── Milestone 8: Refinement loop ─────
│   │       └── ...                    # Cycles, scoped recompilation
│   │
│   └── communication-protocol/         # ── EXISTING: Early experiments ─────
│       └── hello-world.py             # ToolSpec, ToolRegistry, LocalToolClient
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Existing: shared fixtures
│   ├── pytest.ini
│   ├── test_adapter.py                # Existing: Memgraph adapter tests
│   ├── test_domain.py                 # Existing: domain model tests
│   ├── test_persistence.py            # Existing: persistence tests
│   │
│   └── graph/                          # ── NEW: Graph tests ────────────────
│       ├── __init__.py                                          # (M1)
│       ├── conftest.py                # Shared graph test fixtures            (M1)
│       ├── test_m1_basic_graph.py     # State, nodes, edges                  (M1)
│       ├── test_m2_router.py          # Conditional routing                  (M2)
│       ├── test_m3_human_loop.py      # Interrupt, resume, approve/reject    (M3)
│       ├── test_m4_fanout.py          # Fan-out, fan-in, parallel voices     (M4)
│       ├── test_m5_subgraphs.py       # Subgraph wiring, state mapping       (M5)
│       ├── test_m6_real_tools.py      # Integration with real tools + LLM    (M6)
│       ├── test_m7_persistence.py     # Save/load/list projects              (M7)
│       └── test_m8_refinement.py      # Refinement loop, scoped compile      (M8)
│
└── examples/
    ├── demo_twinkle.py                # Existing: basic rendering demo
    ├── demo_twinkle_multipart.py      # Existing: multipart rendering
    ├── demo_render_from_graph.py      # Existing: render from Memgraph
    ├── demo_sketch_to_score.py        # Existing: full intent pipeline demo
    ├── demo_graph_e2e.py              # NEW: End-to-end graph demo            (M6)
    ├── demo_save_load.py              # NEW: Multi-session persistence demo   (M7)
    └── demo_refinement.py             # NEW: Refinement loop demo             (M8)
```

### What's already built (you won't touch these):

| Package | What it does | Files |
|---------|-------------|-------|
| `src/symbolic_music/domain/` | Immutable Pydantic domain models | `models.py` — CompositionSpec, TrackSpec, SectionSpec, NoteEvent, Pitch, etc. |
| `src/symbolic_music/persistence/` | Memgraph read/write with content-addressed versioning | `adapter.py`, `reader.py`, `writer.py`, `types.py` |
| `src/symbolic_music/rendering/` | Domain IR → music21 Score → MIDI/XML | `music21.py` — `render_composition()` |
| `src/intent/` | Sketch → Plan → Compile pipeline | `sketch_models.py`, `plan_models.py`, `planner.py`, `compiler.py`, `compiler_interface.py` |
| `src/tools/` | Centralized tool definitions for agent consumption | `project_tools.py` (done), `intent_tools.py` (M6), `music_tools.py` (M6), `persistence_tools.py` (M7) |

### What you're building (the tutorial):

| Package | What it does | Key files |
|---------|-------------|-----------|
| `src/tools/` | Tool stubs filled in as you go | `intent_tools.py` (M6), `music_tools.py` (M6), `persistence_tools.py` (M7) |
| `src/graph/mN/` | Each milestone is a self-contained package | `state.py`, `graph_builder.py`, `nodes/`, barrel `__init__.py` |
| `tests/graph/` | One test file per milestone | 8 test files |

### Growth by milestone:

Each milestone is self-contained in `src/graph/mN/` with its own state, nodes, and graph_builder.

```
M1:  src/graph/m1/__init__.py, state.py, graph_builder.py
     src/graph/m1/nodes/__init__.py, presenter.py
     tests/graph/test_m1_basic_graph.py

M2:  src/graph/m2/__init__.py, state.py, graph_builder.py
     src/graph/m2/nodes/__init__.py, intent_router.py, stub_nodes.py
     tests/graph/test_m2_router.py

M3:  src/graph/m3/__init__.py, state.py, graph_builder.py
     src/graph/m3/nodes/__init__.py, mock_planner.py, plan_review.py
     tests/graph/test_m3_human_loop.py

M4:  src/graph/m4/__init__.py, state.py, graph_builder.py
     src/graph/m4/nodes/__init__.py, compile_voice.py, assembler.py
     tests/graph/test_m4_fanout.py

M5:  src/graph/m5/__init__.py, state.py, graph_builder.py
     src/graph/m5/subgraphs/__init__.py, creation.py
     tests/graph/test_m5_subgraphs.py

M6:  src/graph/m6/ ...
     src/tools/intent_tools.py, music_tools.py
     tests/graph/test_m6_real_tools.py
     examples/demo_graph_e2e.py

M7:  src/graph/m7/ ...
     src/tools/persistence_tools.py
     tests/graph/test_m7_persistence.py
     examples/demo_save_load.py

M8:  src/graph/m8/ ...
     tests/graph/test_m8_refinement.py
     examples/demo_refinement.py
```

---

## How This Tutorial Works

Each milestone teaches **one LangGraph concept** by building a **working piece of your real system**.
Each milestone is self-contained — it has its own folder, state, and graph. Concepts build on each other, but the code doesn't. By the end, you have the patterns to build the full graph from the component diagram.

**For each milestone:**
- 📖 **Concept** — what you're learning and why it matters
- 🗺️ **Where it fits** — how this connects to the architecture diagram
- 🔨 **What AI provides** — tests, boilerplate, utilities (the scaffolding)
- ✏️ **What you build** — the core logic (the learning)
- ✅ **Verify** — run this, see that
- 🔗 **Connect the dots** — what you just built in the context of the full system

**Convention:** Each milestone is self-contained in its own folder: `src/graph/m1/`, `src/graph/m2/`, etc. Each has its own `state.py`, `graph_builder.py`, `nodes/`, and barrel `__init__.py`. Tests live in `tests/graph/` with one file per milestone. This means milestones don't interfere with each other — you can jump between them freely.

---

## The Big Picture

Here's the full system you're building, with milestones mapped to components:
```aiignore
Phase 1: LangGraph Patterns
  M1: Basic graph flow
  M2: Conditional routing  
  M3: Human-in-the-loop
  M4: Parallel execution
  M5: Subgraph composition
  M6: Real tool integration
  M7: Persistence
  M8: Refinement cycles

Phase 2: Framework Integration
  M9:  ToolSpec + Registry (tool contracts, Pydantic in/out)
  M10: InstrumentedGraph + StateMediator (observability, state routing)
  M11: PlanOrchestrator integration (DAG lifecycle, approval policies)
  M12: Prompt templates + LLM swap (structured output, fallbacks, agent mode)

When you're ready to build the real system, you'll think:

"I need human review → use M3 pattern"
"I need parallel voices → use M4 pattern"
"I need persistence → use M7 pattern"
"I need a tool contract → use M9 pattern"
"I need observability → use M10 pattern"
"I need DAG orchestration → use M11 pattern"
"I need LLM with fallback → use M12 pattern"
```

---




```
┌─────────────────────────────────────────────────────────────────┐
│                        PARENT GRAPH                              │
│                                                                  │
│  User Message → Intent Router (M2) ──┬── "new" ──→ [Creation]   │
│                                      ├── "refine" → [Refinement] │
│                                      ├── "load"  ──→ Load (M7)   │
│                                      ├── "save"  ──→ Save (M7)   │
│                                      └── "query" ──→ Answerer    │
│                                                                  │
│  ┌─── Creation Subgraph (M5) ──────────────────────────┐        │
│  │  Sketch Parser (M6) → Seed Resolver (M6)            │        │
│  │       → Planner (M6) → Plan Review (M3) ──┐         │        │
│  │                          ▲    │ (interrupt) │         │        │
│  │                          └────┘   approve   │         │        │
│  │                                     │       │         │        │
│  │                              Voice Compiler ×N (M4)   │        │
│  │                                     │                 │        │
│  │                              Assembler (M4)           │        │
│  │                                     │                 │        │
│  │                              Renderer (M6)            │        │
│  │                                     │                 │        │
│  │                              Presenter (M1)           │        │
│  └───────────────────────────────────────────────────────┘        │
│                                                                  │
│  ┌─── Refinement Subgraph (M8) ────────────────────────┐        │
│  │  Scope Classifier → Plan Refiner → Plan Review       │        │
│  │       → Scoped Compile (fan-out) → Assembler          │        │
│  │       → Renderer → Presenter                          │        │
│  └───────────────────────────────────────────────────────┘        │
│                                                                  │
│  Checkpointer (M3/M7)                                           │
└──────────────────────────────────────────────────────────────────┘

Legend: (M1) = Milestone 1, (M2) = Milestone 2, etc.
```

---

## Milestone 1: The Simplest Graph That Does Something
**LangGraph concept:** State, nodes, edges, `StateGraph`, `invoke()`

### 📖 Concept

A LangGraph graph is three things:
1. **State** — a `TypedDict` that holds all data flowing through the graph
2. **Nodes** — Python functions that read state, do work, write state
3. **Edges** — connections between nodes that define execution order

Every node receives the full state and returns a partial dict of updates. LangGraph merges the updates into state automatically.

```python
# A node is just a function:
def my_node(state: MyState) -> dict:
    # read from state
    name = state["name"]
    # do work
    greeting = f"Hello, {name}!"
    # return updates (only the fields you're changing)
    return {"greeting": greeting}
```

### 🗺️ Where it fits

You're building the **Presenter** node and the basic graph skeleton. Every future milestone adds nodes and edges to this foundation.

### 🔨 What AI provides

- `src/graph/__init__.py` — package init
- `src/graph/state.py` — the `MusicGraphState` TypedDict (starter version, we'll grow it)
- `tests/graph/test_m1_basic_graph.py` — tests that verify your graph works

### ✏️ What you build

- `src/graph/nodes/presenter.py` — a node that formats a summary message
- `src/graph/graph_builder.py` — wire up a 3-node linear graph:
  `start → process_node → presenter → END`

### ✅ Verify

```bash
pytest tests/graph/test_m1_basic_graph.py -v
```

You should see:
- State flows through all 3 nodes
- Presenter produces a formatted message
- `invoke()` returns the final state with all fields populated

### 🔗 Connect the dots

You just built the skeleton that every future milestone extends. The state will grow. The nodes will multiply. But the pattern — define state, write node functions, wire edges — is the same all the way through.

---

## Milestone 2: The Router
**LangGraph concept:** Conditional edges, state-based routing

### 📖 Concept

So far, your graph is a straight line: A → B → C. But your real system needs branching — the Intent Router looks at the user's message and decides which path to take.

LangGraph handles this with **conditional edges**: instead of `node_a → node_b`, you write `node_a → function_that_picks_next_node`.

```python
# A routing function inspects state and returns a node name:
def route_intent(state: MusicGraphState) -> str:
    if state["intent_type"] == "new_sketch":
        return "sketch_parser"
    elif state["intent_type"] == "question":
        return "answerer"
    ...

# Wire it:
graph.add_conditional_edges("intent_router", route_intent)
```

### 🗺️ Where it fits

You're building the **Intent Router** — the single entry point for every user message. This is the top of the architecture diagram, the first decision point.

### 🔨 What AI provides

- `tests/graph/test_m2_router.py` — tests that send different messages and verify correct routing
- Stub nodes for each destination (just return a marker so you can verify routing)

### ✏️ What you build

- `src/graph/nodes/intent_router.py` — a node that classifies the user's message into an `intent_type`
  - For now, use keyword matching (not LLM). "write me" → `new_sketch`, "make the" → `plan_refine`, "save" → `save_project`, etc.
  - Later (M6) we'll swap this for an LLM classifier
- Update `graph_builder.py` — add the router node and conditional edges to route to different stub destinations

### ✅ Verify

```bash
pytest tests/graph/test_m2_router.py -v
```

You should see:
- "Write me a rock tune" → routes to `creation` path
- "Make the chorus busier" → routes to `refinement` path
- "Save this" → routes to `save` path
- "What key is the bridge in?" → routes to `answerer` path

### 🔗 Connect the dots

Every user message now enters through the router. The graph is no longer linear — it branches. This is the skeleton of the parent graph from the component diagram. Each branch is currently a stub; future milestones fill them in.

**Key insight:** The router is *state-aware*. It doesn't just look at the message — it also checks whether there's a plan loaded, a composition compiled, etc. This is what makes "make it busier" work differently when there's no plan vs. when there is one.

---

## Milestone 3: The Human in the Loop
**LangGraph concept:** `interrupt()`, `MemorySaver`, `Command(resume=...)`, approve/reject cycle

### 📖 Concept

The graph can **pause** at a specific node, hand control to the user, and **resume** when the user responds. This requires two things:

1. **A checkpointer** (`MemorySaver`) — saves graph state so it can be restored on resume
2. **`interrupt()`** — called inside a node to pause execution and receive the human's response

There are two approaches to interrupts in LangGraph:

- **Static** (`interrupt_before=["node"]` in `compile()`) — pauses before a node runs. Simple but the node can't receive the resume value directly.
- **Dynamic** (`interrupt()` inside the node) — the node controls when to pause and directly receives the resume value. This is the production-ready approach.

This milestone uses the **dynamic** approach:

```python
from langgraph.types import interrupt

def plan_review(state: MusicGraphState) -> dict:
    # interrupt() does two things:
    #   1. PAUSES the graph — its argument is sent back to the caller
    #   2. RETURNS the resume value when the user calls Command(resume=...)
    human_response = interrupt({"plan": state["plan"]})
    return {"approved": human_response["approved"]}
```

The caller's side:

```python
# Step 1: Invoke — runs until interrupt() pauses
result = app.invoke(input, config={"configurable": {"thread_id": "1"}})
# result contains the plan (mock_planner ran before the interrupt)

# Step 2: Resume with the human's decision
result = app.invoke(
    Command(resume={"approved": True}),
    config={"configurable": {"thread_id": "1"}}
)
# interrupt() returns {"approved": True}, plan_review continues
```

### 🗺️ Where it fits

You're building the **Plan Review** node — the human checkpoint where the user sees the plan and approves, rejects, or tweaks it. This is the heart of the human-in-the-loop pattern.

### The graph

```
START → mock_planner → plan_review → conditional → ...
              ↑         (interrupt()        │
              │          pauses here)        │
              │     approved → stub_compiler │
              └──── rejected ───────────────┘
```

### 🔨 What AI provides

- `tests/graph/test_m3_human_loop.py` — 7 tests across 4 classes:
  - `TestGraphPauses` — plan exists after first invoke, has expected keys
  - `TestApprove` — resume with `approved=True` reaches stub_compiler
  - `TestReject` — reject loops back; reject-then-approve works
  - `TestStatePreserved` — user_message and plan survive across interrupt
- `src/graph/m3/state.py` — state with `plan`, `approved`, `compiled` fields
- `src/graph/m3/nodes/__init__.py` — barrel exports

### ✏️ What you build

- `src/graph/m3/nodes/mock_planner.py` — returns `{"plan": {...}}` with a fake plan (must have `genre` and `voices` keys)
- `src/graph/m3/nodes/plan_review.py` — calls `interrupt()` to pause, receives resume value, returns `{"approved": ...}`
- `src/graph/m3/graph_builder.py`:
  - 3 nodes: `mock_planner`, `plan_review`, `stub_compiler`
  - Edges: `START → mock_planner → plan_review`
  - Conditional edge after `plan_review`: approved → `stub_compiler` → `END`, rejected → `mock_planner` (cycle)
  - Compile with `MemorySaver()` checkpointer
  - `stub_compiler` just returns `{"compiled": True}`

### ✅ Verify

```bash
pytest tests/graph/test_m3_human_loop.py -v
```

You should see:
- Graph pauses at plan_review (plan exists in state)
- Approve → stub_compiler runs → `compiled=True`
- Reject → loops back to mock_planner → pauses again
- Reject then approve → stub_compiler runs
- State (user_message, plan) preserved across interrupt

### 🔗 Connect the dots

You now have the core collaboration pattern. The AI proposes, the human reviews, and the system responds to the human's decision.

**Key insight:** `interrupt()` is both a "send" and a "receive". Its argument is what the human sees; its return value is what the human sends back. The checkpointer is what makes this possible — without it, the graph loses state when it pauses.

---

## Milestone 4: Fan-Out / Fan-In
**LangGraph concept:** `Send()`, dynamic parallel execution, `Annotated[list, operator.add]` reducers

### 📖 Concept

Your compiler generates each voice independently — drums, bass, piano, guitar. These can run in parallel. LangGraph's `Send()` lets you dynamically spawn N parallel nodes based on runtime data.

```python
# A routing function that spawns parallel nodes:
def fan_out_voices(state: MusicGraphState) -> list[Send]:
    voices = state["plan"].voice_plan.voices
    return [
        Send("compile_voice", {"voice": v, "plan": state["plan"]})
        for v in voices
    ]

# The fan-in uses a reducer on the state field:
class MusicGraphState(TypedDict):
    voice_sections: Annotated[list[dict], operator.add]  # accumulates results
```

Each `compile_voice` node runs independently and appends its result to `voice_sections`. When all are done, the next node (Assembler) sees the full list.

### 🗺️ Where it fits

You're building the **Voice Compiler × N** and **Assembler** — the parallel compilation step from the Creation Subgraph. This is the most architecturally impressive part of the graph for a portfolio.

### 🔨 What AI provides

- `tests/graph/test_m4_fanout.py` — tests that:
  - Fan out to N voice compilers based on the plan's voice count
  - Each voice compiler produces independent results
  - Assembler receives all results and merges them
  - Verify ordering doesn't matter (parallel execution)
- A mock plan with 4 voices for testing

### ✏️ What you build

- `src/graph/nodes/compile_voice.py` — a node that compiles a single voice
  - For now, use a stub that returns mock section data tagged with the voice ID
  - Later (M6) we'll wire in the real `PatternCompiler`
- `src/graph/nodes/assembler.py` — a node that collects all voice results and assembles them
- Update `graph_builder.py`:
  - Add the fan-out conditional edge using `Send()`
  - Add the `compile_voice` node
  - Add the `assembler` node
  - Wire: plan_review (approved) → fan-out → compile_voice × N → assembler

### ✅ Verify

```bash
pytest tests/graph/test_m4_fanout.py -v
```

You should see:
- 4 voices in plan → 4 compile_voice executions
- Assembler receives 4 results
- Changing the plan to 6 voices → 6 executions (dynamic!)

### 🔗 Connect the dots

You now have parallel execution in your graph. This is a real architectural pattern — not just a demo trick. In a production system, these voice compilations could be distributed across workers. The `Send()` pattern is the same whether you're compiling 4 voices or 40.

**Key insight:** The `Annotated[list, operator.add]` reducer is what makes fan-in work. Each parallel node appends to the list independently. LangGraph handles the merging. This is the same pattern used in map-reduce agent architectures.

---

## Milestone 5: Subgraphs
**LangGraph concept:** Nested `StateGraph`, parent-child state mapping, modular composition

### 📖 Concept

Your graph is getting complex. The creation pipeline (sketch → seed → plan → review → compile → render) is a self-contained workflow. So is the refinement pipeline. LangGraph lets you extract these into **subgraphs** — nested graphs with their own internal structure.

```python
# Define a subgraph:
creation_builder = StateGraph(CreationState)
creation_builder.add_node("sketch_parser", sketch_parser)
creation_builder.add_node("engine", planner)
# ... etc
creation_graph = creation_builder.compile()

# Use it as a node in the parent:
parent_builder = StateGraph(MusicGraphState)
parent_builder.add_node("creation", creation_graph)
parent_builder.add_node("refinement", refinement_graph)
```

### 🗺️ Where it fits

You're extracting the **Creation Subgraph** from your flat graph. This is the left box in the architecture diagram. Later (M8) you'll do the same for the Refinement Subgraph.

### 🔨 What AI provides

- `tests/graph/test_m5_subgraphs.py` — tests that:
  - Parent graph routes to creation subgraph
  - Subgraph runs its internal pipeline
  - State flows correctly between parent and child
  - Subgraph is independently testable
- State type definitions for the subgraph

### ✏️ What you build

- `src/graph/subgraphs/creation.py` — the Creation Subgraph:
  - Extract sketch_parser → planner → plan_review → fan-out → assembler → renderer → presenter
  - All the nodes you built in M1-M4, now inside a subgraph
- Update `graph_builder.py`:
  - Replace the inline creation nodes with the subgraph
  - Wire: intent_router → "new_sketch" → creation subgraph

### ✅ Verify

```bash
pytest tests/graph/test_m5_subgraphs.py -v
```

You should see:
- Parent routes to creation subgraph
- Subgraph runs full pipeline internally
- State returns to parent with sketch, plan, compile_result populated
- Subgraph can also be tested standalone (without parent)

### 🔗 Connect the dots

Your graph is now modular. The creation pipeline is encapsulated — you can test it, reason about it, and modify it independently. This is the same pattern used in production multi-agent systems where different teams own different subgraphs.

**Key insight:** Subgraphs can have their own state type that's a subset of the parent state. This enforces boundaries — the creation subgraph can't accidentally modify refinement-specific fields.

---

## Milestone 6: Wire in the Real Tools
**LangGraph concept:** Tool integration, structured LLM output, replacing stubs with real implementations

### 📖 Concept

Up to now, your nodes have been stubs — returning fake data to test the graph structure. Now you wire in the real tools you already built:

- `DeterministicPlanner.plan()` → Planner node
- `PatternCompiler.compile()` → Voice Compiler node
- `render_composition()` → Renderer node

This is also where you add the **LLM-backed nodes** (Sketch Parser, Intent Router) using structured output — the LLM returns a Pydantic model, not free text.

```python
# LLM with structured output:
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o")
structured_llm = llm.with_structured_output(Sketch)

def sketch_parser(state: MusicGraphState) -> dict:
    sketch = structured_llm.invoke(state["messages"])
    return {"sketch": sketch}
```

### 🗺️ Where it fits

This is where the graph stops being a demo and becomes your real system. Every stub gets replaced with a real implementation. After this milestone, you can type a natural language prompt and get a music21 Score.

### 🔨 What AI provides

- `tests/graph/test_m6_real_tools.py` — integration tests that run the full pipeline
- `src/graph/nodes/sketch_parser.py` — LLM-backed sketch extraction (you review and understand it)
- `src/graph/nodes/seed_resolver.py` — deterministic seed resolution node
- Prompt templates for the LLM nodes
- A `.env.example` for API keys

### ✏️ What you build

- `src/graph/nodes/planner.py` — wire `DeterministicPlanner` into a graph node
  - Read `sketch` and `seed_analysis_text` from state
  - Call `planner.plan(sketch)`
  - Return `{"plan": plan_bundle}`
- `src/graph/nodes/compile_voice.py` — replace stub with real `PatternCompiler` (per-voice)
- `src/graph/nodes/renderer.py` — wire `render_composition()` into a graph node
- Update the creation subgraph to use real nodes
- Update the intent router to use LLM classification (swap keyword matching for structured output)

### ✅ Verify

```bash
# Unit test with deterministic engine (no LLM needed):
pytest tests/graph/test_m6_real_tools.py -v -k "deterministic"

# Integration test with LLM (needs API key):
pytest tests/graph/test_m6_real_tools.py -v -k "llm"

# End-to-end demo:
python examples/demo_graph_e2e.py
```

You should see:
- "Write me a rock tune in A minor" → Sketch → PlanBundle → CompileResult → Score summary
- Real musical output (notes, measures, sections)
- Plan review interrupt works with real plan data

### 🔗 Connect the dots

**This is the milestone where it becomes real.** You type English, the system produces music. Everything before this was graph plumbing. Everything after this adds capabilities to a working system.

**Key insight:** Notice how cleanly the tools plug in. The graph structure didn't change — only the node implementations. This is the payoff of designing the graph first and implementing tools second.

---

## Milestone 7: Persistence — Save and Load
**LangGraph concept:** Checkpointer persistence, tool-based state management, multi-session workflows

### 📖 Concept

Two kinds of persistence, two purposes:

1. **Checkpointer** (automatic) — saves conversation state after every node. Enables resume-after-interrupt and crash recovery. You already set this up in M3 with `MemorySaver`. Now you'll upgrade to `SqliteSaver` for durability.

2. **Project persistence** (explicit) — saves musical artifacts (Sketch, PlanBundle, CompositionSpec) to Memgraph with versioning and lineage. This is what "Save this as Bossa Rock v2" does.

```python
# Checkpointer upgrade:
from langgraph.checkpoint.sqlite import SqliteSaver
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

# Project save tool:
def save_project(state: MusicGraphState) -> dict:
    version = persist_to_memgraph(
        name=state["project_name"],
        sketch=state["sketch"],
        plan=state["plan"],
        compile_result=state["compile_result"],
    )
    return {"project_version": version}
```

### 🗺️ Where it fits

You're building the **Save Project**, **Load Project**, and **List Projects** nodes from the parent graph. This enables Use Cases 4 and 6 — multi-session workflows.

### 🔨 What AI provides

- `tests/graph/test_m7_persistence.py` — tests for save/load/list
- `src/graph/nodes/project_save.py` — Memgraph persistence logic (compound tool)
- `src/graph/nodes/project_load.py` — Memgraph hydration logic
- `src/graph/nodes/project_list.py` — Memgraph query logic
- Memgraph schema setup for project storage

### ✏️ What you build

- Wire save/load/list nodes into the parent graph
- Add conditional edges from intent router: `"save_project"` → save node → presenter
- Add conditional edges: `"load_project"` → load node → presenter
- Upgrade checkpointer from `MemorySaver` to `SqliteSaver`
- Test the full save → close → reopen → load → refine workflow

### ✅ Verify

```bash
pytest tests/graph/test_m7_persistence.py -v

# Multi-session demo:
python examples/demo_save_load.py
```

You should see:
- Create a composition, save it as "My Rock Tune v1"
- Start a new session, load "My Rock Tune"
- State is fully hydrated — plan, composition, everything
- Refine and save as v2
- List projects shows both versions

### 🔗 Connect the dots

Your system now has memory across sessions. This is the difference between a toy demo and a real creative tool. The user's work persists, versions accumulate, and they can pick up where they left off.

**Key insight:** The checkpointer and Memgraph serve different timescales. Checkpointer = "I refreshed my browser, where was I?" Memgraph = "I want to come back to this project next week."

---

## Milestone 8: The Refinement Loop
**LangGraph concept:** Graph cycles, scoped recompilation, subgraph reuse

### 📖 Concept

The user has a composition and wants to change something. This is a **cycle** in the graph — the system goes back through planning and compilation, but only for the parts that changed.

```python
# Scoped fan-out — only recompile changed voices:
def fan_out_changed_voices(state: MusicGraphState) -> list[Send]:
    changed = state["changed_voice_ids"]
    return [
        Send("compile_voice", {"voice": v, "plan": state["plan"]})
        for v in state["plan"].voice_plan.voices
        if v.voice_id in changed
    ]
```

The Assembler then **merges** new voice results with the previous compilation — unchanged voices are preserved.

### 🗺️ Where it fits

You're building the **Refinement Subgraph** — the right box in the architecture diagram. This handles Use Case 3 ("make the chorus busier") and the refinement path from Use Case 4 (load → refine → save).

### 🔨 What AI provides

- `tests/graph/test_m8_refinement.py` — tests for:
  - Scope classification (what changed?)
  - Plan refinement (apply the change)
  - Scoped recompilation (only changed voices)
  - Merge with previous result (unchanged voices preserved)
- `src/graph/nodes/scope_classifier.py` — determines what the user wants to change
- `src/graph/subgraphs/refinement.py` — the Refinement Subgraph skeleton

### ✏️ What you build

- `src/graph/nodes/plan_refiner.py` — wire `DeterministicPlanner.refine()` into a graph node
- Complete the Refinement Subgraph:
  - scope_classifier → plan_refiner → plan_review → scoped fan-out → assembler (merge mode) → renderer
- Update `src/graph/nodes/assembler.py` — add merge logic (preserve unchanged voices from previous `compile_result`)
- Wire the refinement subgraph into the parent graph
- Add conditional edge from intent router: `"plan_refine"` → refinement subgraph

### ✅ Verify

```bash
pytest tests/graph/test_m8_refinement.py -v

# Full refinement demo:
python examples/demo_refinement.py
```

You should see:
- "Make the chorus drums busier" → only drums recompiled, other voices preserved
- "Add a percussion track" → new voice added, existing voices untouched
- Plan review shows a **diff** (what changed vs. previous plan)
- Iteration counter increments

### 🔗 Connect the dots

Your system now supports iterative creative workflows. The user can refine endlessly, and each refinement is surgical — only the affected parts are recomputed. This is the full creative loop from the use cases.

**Key insight:** The Refinement Subgraph shares nodes with the Creation Subgraph (plan_review, compile_voice, assembler, renderer). The difference is the entry point (scope classifier vs. sketch parser) and the compilation scope (partial vs. full). Subgraphs let you reuse without duplication.

---

# Phase 2: Framework Integration (M9–M12)

Phase 1 (M1–M8) teaches LangGraph patterns using plain `StateGraph` and direct function calls.
Phase 2 bridges to the **reusable framework** in `src/framework/langgraph_ext/` — the tool client, instrumented graph, state mediator, and plan orchestrator that were built separately. These milestones wire that infrastructure into the graph code so the system is production-shaped.

**Key principle:** Every milestone in Phase 2 keeps deterministic logic. No LLM calls until M12. You define the contracts, spoof the AI, then swap it in.

### Existing framework inventory

| Component | Location | What it does |
|-----------|----------|--------------|
| `ToolSpec` | `framework/langgraph_ext/tool_client/spec.py` | Pydantic in/out models + handler = one tool contract |
| `ToolRegistry` | `framework/langgraph_ext/tool_client/registry.py` | Catalog of all tools, JSON Schema export for MCP |
| `LocalToolClient` | `framework/langgraph_ext/tool_client/client.py` | Validates in/out, wraps results in `ToolResultEnvelope` |
| `ToolResultEnvelope` | `framework/langgraph_ext/tool_client/envelope.py` | Provenance metadata on every tool call |
| `InstrumentedGraph` | `framework/langgraph_ext/instrumented_graph.py` | `StateGraph` subclass with interceptor hooks + middleware |
| `Interceptor` | (same file) | Observe-only hooks (logging, metrics) |
| `Middleware` | (same file) | Transform node results (state mediation) |
| `StateMediator` | `framework/langgraph_ext/middleware/state_mediator.py` | Routes `ToolResultEnvelope` → state field updates |
| `PlanOrchestrator` | `framework/langgraph_ext/planning/orchestrator.py` | Step-based DAG lifecycle driver (pure Python) |
| `PlanGraph` / `SubPlan` | `framework/langgraph_ext/planning/models.py` | DAG data model with status lifecycle |
| `ScopeRegistry` | `framework/langgraph_ext/planning/registry.py` | Maps scope types → planners + executors |
| `ApprovalPolicy` | `framework/langgraph_ext/planning/approval.py` | Controls human-in-the-loop at sub-plan level |
| `src/tools/` stubs | `src/tools/intent_tools.py`, `music_tools.py`, `persistence_tools.py` | Placeholder files for domain tool definitions |

---

## Milestone 9: ToolSpec + Registry — Wire the Tool Library
**Framework concept:** `ToolSpec`, `ToolRegistry`, `LocalToolClient`, `ToolResultEnvelope`

### 📖 Concept

Every domain operation (plan, compile, refine, save, load, render) becomes a `ToolSpec` — a frozen contract with Pydantic input/output models and a handler function. Graph nodes call `LocalToolClient.call(name, args)` instead of calling domain logic directly. Every result comes back in a `ToolResultEnvelope` with provenance metadata (timing, input hash, success/failure).

This is the **tool library** — independent of any specific graph or use case. An LLM agent could use these same tools in a completely different workflow.

```python
# What a ToolSpec looks like:
ToolSpec(
    name="plan_composition",
    description="Generate a PlanBundle from a Sketch",
    input_model=PlanCompositionInput,   # Pydantic model
    output_model=PlanCompositionOutput, # Pydantic model
    handler=plan_composition_handler,   # wraps DeterministicPlanner.plan()
)
```

### 🗺️ Where it fits

You're filling in the `src/tools/` stubs (`intent_tools.py`, `music_tools.py`, `persistence_tools.py`) and registering them in a `ToolRegistry`. Then updating graph nodes to call tools through `LocalToolClient` instead of directly.

### 🔨 What AI provides

- `tests/graph/test_m9_tool_library.py` — tests for:
  - Each ToolSpec validates inputs and outputs
  - Registry catalogs all tools
  - LocalToolClient wraps results in envelopes
  - Graph nodes work identically when calling through the client
- Pydantic input/output model skeletons for each tool
- Updated graph builder wiring

### ✏️ What you build

- Complete `src/tools/intent_tools.py` — ToolSpecs for: `parse_sketch`, `plan_composition`, `compile_composition`, `refine_plan`
- Complete `src/tools/music_tools.py` — ToolSpecs for: `render_composition`, `validate_composition`
- Complete `src/tools/persistence_tools.py` — ToolSpecs for: `save_project`, `load_project`, `list_projects`
- Register all specs in a `build_registry()` function
- Update M9 graph nodes to call `LocalToolClient.call(name, args)`

### ✅ Verify

```bash
pytest tests/graph/test_m9_tool_library.py -v
```

You should see:
- Every tool's Pydantic models validate correctly
- `LocalToolClient` returns `ToolResultEnvelope` with metadata
- Full pipeline produces identical results when called through the tool client
- Registry catalogs all tools with JSON Schema export

### 🔗 Connect the dots

Your tools are now a **menu** — discoverable, validated, and wrapped with metadata. When you add an LLM agent later, it can browse this menu and call any tool. The contracts are enforced whether the caller is a hardcoded node or an autonomous agent.

**Key insight:** The tool library is independent of the graph topology. The same `plan_composition` tool can be called from the creation subgraph, the refinement subgraph, or a future agent that you haven't designed yet.

---

## Milestone 10: InstrumentedGraph + StateMediator
**Framework concept:** `InstrumentedGraph`, `Interceptor`, `Middleware`, `StateMediator`

### 📖 Concept

Replace `StateGraph` with `InstrumentedGraph` in the graph builder. Every node automatically gets interceptor hooks (logging, metrics) and middleware (state mediation). The `StateMediator` inspects `ToolResultEnvelope` metadata and routes results to the correct state fields.

```python
# Before (M8): nodes manually return state patches
def planner(state):
    plan = _planner.plan(state["sketch"])
    return {"plan": plan}

# After (M10): nodes return tool envelopes, mediator handles state
def planner(state):
    return tool_client.call("plan_composition", {"sketch": state["sketch"]})
    # StateMediator routes the envelope → {"plan": ...}
```

### 🗺️ Where it fits

You're upgrading the graph builder to use `InstrumentedGraph` and wiring `StateMediator` handlers for each tool. Nodes become thinner — they call tools and return envelopes. The mediator does the state routing.

### 🔨 What AI provides

- `tests/graph/test_m10_instrumented.py` — tests for:
  - Logging interceptor captures node events
  - Metrics interceptor tracks timing
  - StateMediator correctly routes tool results to state fields
  - Pipeline produces identical results with instrumentation
- StateMediator handler registrations for each tool

### ✏️ What you build

- Update `graph_builder.py` to use `InstrumentedGraph` instead of `StateGraph`
- Add `LoggingInterceptor` and `MetricsInterceptor`
- Register `StateMediator` handlers: `plan_composition → {"plan": ...}`, etc.
- Simplify node functions to return `ToolResultEnvelope` directly

### ✅ Verify

```bash
pytest tests/graph/test_m10_instrumented.py -v
```

You should see:
- Node execution times logged
- State correctly populated from envelope metadata
- Full pipeline works identically to M9, now with observability

### 🔗 Connect the dots

Your graph is now **observable**. Every node call is timed, logged, and the state routing is declarative (registered handlers) instead of imperative (manual dict construction). When something breaks in production, you'll see exactly which tool failed, what inputs it received, and how long it took.

**Key insight:** Nodes are now just "call a tool and return the envelope." All the intelligence about where results go lives in the mediator registrations. This makes nodes trivially swappable and testable.

---

## Milestone 11: PlanOrchestrator Integration
**Framework concept:** `PlanOrchestrator`, `PlanGraph`, `SubPlan`, `ScopeRegistry`, `ApprovalPolicy`

### 📖 Concept

The `PlanOrchestrator` is a pure Python class that drives a DAG of sub-plans through a lifecycle: `draft → approved → executing → done`. It handles approval policies, refinement with cascade invalidation, and step-based execution. In this milestone, you wrap it as a LangGraph node.

The orchestrator replaces the linear `planner → compiler` pipeline with a DAG-based workflow:
- Each sub-plan (harmony, groove, compilation) is a node in the DAG
- Dependencies are explicit (compilation depends on harmony + groove)
- Refinement invalidates only downstream sub-plans
- Approval policies control which sub-plans need human review

```python
# The orchestrator drives the plan DAG
registry = ScopeRegistry()
registry.register("harmony_plan", HarmonyPlanner(), HarmonyExecutor())
registry.register("groove_plan", GroovePlanner(), GrooveExecutor())
registry.register("compilation", NoOpPlanner(), CompileExecutor())

orchestrator = PlanOrchestrator(registry=registry, approval_policy=AlwaysApprove())
orchestrator.load_plan(plan_graph)
orchestrator.run()  # drives to completion
```

### 🗺️ Where it fits

You're building a new `orchestrated_creation` subgraph that uses `PlanOrchestrator` instead of a linear pipeline. This is the production-shaped version of the creation flow.

### 🔨 What AI provides

- `tests/graph/test_m11_orchestrator.py` — tests for:
  - PlanOrchestrator drives plan DAG to completion
  - Refinement invalidates downstream sub-plans
  - Approval policies block execution until approved
  - Graph node wraps orchestrator correctly
- Domain planner/executor registrations for `ScopeRegistry`

### ✏️ What you build

- Domain planners for `ScopeRegistry`: `HarmonyPlanner`, `GroovePlanner`, etc.
- Domain executors: `CompileExecutor` wrapping `PatternCompiler`
- `orchestrated_creation` subgraph that uses `PlanOrchestrator`
- Wire into parent graph alongside the existing creation subgraph

### ✅ Verify

```bash
pytest tests/graph/test_m11_orchestrator.py -v
```

You should see:
- Plan DAG executes in dependency order
- Refinement re-plans targeted scopes and invalidates downstream
- Human-in-the-loop approval blocks at the right points
- Full pipeline produces identical musical output

### 🔗 Connect the dots

The plan framework gives you **surgical refinement**. Instead of recompiling everything, the orchestrator knows which sub-plans are stale and only re-executes those. Combined with the tool library (M9) and observability (M10), you have a production-grade creative pipeline.

**Key insight:** The `PlanOrchestrator` is pure Python — no LangGraph dependency. The graph node is a thin wrapper. This means the orchestration logic is testable without any graph infrastructure.

---

## Milestone 12: Prompt Templates + LLM Swap
**Framework concept:** Structured output, prompt templates, deterministic fallbacks, agent mode

### 📖 Concept

Every node that *could* be LLM-backed gets three things:
1. A **prompt template** (what you'd ask the LLM)
2. A **Pydantic response model** (structured output — already defined in M9)
3. A **deterministic fallback** (what the system does if the LLM is unavailable)

You build a `DeterministicFallback` wrapper: it tries the LLM, falls back to the rule-based logic. Then you swap in real LLM calls one node at a time.

```python
# The pattern for every LLM-backed node:
class SketchParserTool:
    prompt_template = "Extract structured music parameters from: {user_message}..."
    output_model = SketchParserOutput  # Pydantic

    def __call__(self, input: SketchParserInput) -> SketchParserOutput:
        try:
            return self.llm.with_structured_output(self.output_model).invoke(
                self.prompt_template.format(**input.model_dump())
            )
        except Exception:
            return self.deterministic_fallback(input)
```

### 🗺️ Where it fits

You're adding LLM integration to nodes that benefit most from it:
1. **Intent router** — natural language understanding
2. **Sketch parser** — free-text → structured music parameters
3. **Scope classifier** — what the user wants to change

Other nodes (planner, compiler, renderer) stay deterministic — they're domain logic, not interpretation.

### 🔨 What AI provides

- `tests/graph/test_m12_llm_swap.py` — tests for:
  - Prompt templates produce valid structured output
  - Deterministic fallback works when LLM is unavailable
  - Pipeline works with spoofed LLM responses
  - Pipeline works with real LLM (integration test, skipped without API key)
- Prompt template definitions for each LLM-backed node

### ✏️ What you build

- Prompt templates for intent_router, sketch_parser, scope_classifier
- `DeterministicFallback` wrapper
- LLM tool integration using the ToolSpec pattern from M9
- Agent mode: an LLM that can browse the tool registry and choose which tools to call

### ✅ Verify

```bash
# Without LLM (deterministic fallback)
pytest tests/graph/test_m12_llm_swap.py -v

# With LLM (requires API key)
pytest tests/graph/test_m12_llm_swap.py -v --run-llm
```

You should see:
- All tests pass with deterministic fallbacks (no API key needed)
- With an LLM, the system handles natural language more flexibly
- The same ToolSpec contracts are enforced whether the caller is deterministic or LLM

### 🔗 Connect the dots

Your system is now **production-shaped**: tool contracts, observability, DAG orchestration, and LLM integration — all with deterministic fallbacks. The LLM adds flexibility, but the system works without it. This is the architecture you'll deploy.

**Key insight:** The LLM is a **component**, not the system. It interprets user intent and classifies scope. The planner, compiler, and renderer are deterministic — they produce reliable, repeatable musical output. The LLM makes the interface more natural, but the music generation doesn't depend on it.

---

## What You'll Have at the End

### After Phase 1 (M1–M8):

```
✅ Parent graph with intent routing (7 intent types)
✅ Creation subgraph (sketch → plan → compile → present)
✅ Refinement subgraph (classify → refine → scoped compile → merge)
✅ Human-in-the-loop plan review with approve/reject/tweak
✅ Parallel voice compilation with dynamic fan-out
✅ Real tools: DeterministicPlanner, PatternCompiler
✅ Project persistence: save/load/list via MusicStore (InMemoryStore)
✅ Checkpointing: multi-turn workflows, session persistence
✅ Iterative refinement with scoped recompilation
```

### After Phase 2 (M9–M12):

```
✅ ToolSpec contracts for every domain operation (Pydantic in/out + handler)
✅ ToolRegistry with JSON Schema export (MCP-ready)
✅ LocalToolClient with ToolResultEnvelope (provenance metadata)
✅ InstrumentedGraph with logging and metrics interceptors
✅ StateMediator routing tool results to state fields
✅ PlanOrchestrator driving DAG-based plan lifecycle
✅ ScopeRegistry with domain planners and executors
✅ ApprovalPolicy controlling human-in-the-loop at sub-plan level
✅ Prompt templates with Pydantic structured output
✅ DeterministicFallback for every LLM-backed node
✅ Agent mode: LLM browses tool registry and chooses tools
```

### LangGraph features demonstrated:

| Feature | Milestone |
|---------|-----------|
| StateGraph, nodes, edges | M1 |
| Conditional edges | M2 |
| Human-in-the-loop (interrupt) | M3 |
| Dynamic fan-out (Send) | M4 |
| Fan-in (reducers) | M4 |
| Subgraphs | M5 |
| Real tool integration | M6 |
| Checkpointer persistence | M3, M7 |
| Graph cycles | M8 |
| Scoped recompilation | M8 |
| ToolSpec + ToolRegistry | M9 |
| LocalToolClient + ToolResultEnvelope | M9 |
| InstrumentedGraph + Interceptors | M10 |
| StateMediator middleware | M10 |
| PlanOrchestrator as a node | M11 |
| ScopeRegistry + ApprovalPolicy | M11 |
| Structured LLM output | M12 |
| Prompt templates + fallbacks | M12 |
| Agent tool selection | M12 |

### Portfolio story:

> "I designed and built a multi-phase creative AI agent using LangGraph. It turns natural language descriptions into symbolic music compositions through a pipeline of LLM interpretation, deterministic planning, parallel compilation, and human-in-the-loop review. The system supports iterative refinement with scoped recompilation, multi-session persistence, and a pluggable tool library with MCP-ready contracts. Every tool call is instrumented with provenance metadata, and the plan lifecycle is driven by a DAG orchestrator with configurable approval policies. LLM integration uses structured output with deterministic fallbacks — the system works without an API key but benefits from one."

---

## Estimated Timeline

### Phase 1: LangGraph Patterns

| Milestone | Estimated time | Cumulative |
|-----------|---------------|------------|
| M1: Basic graph | 30 min | 30 min |
| M2: Router | 45 min | 1h 15m |
| M3: Human-in-the-loop | 45 min | 2h |
| M4: Fan-out / Fan-in | 1 hr | 3h |
| M5: Subgraphs | 1 hr | 4h |
| M6: Real tools | 1.5 hr | 5h 30m |
| M7: Persistence | 1.5 hr | 7h |
| M8: Refinement loop | 1.5 hr | 8h 30m |

### Phase 2: Framework Integration

| Milestone | Estimated time | Cumulative |
|-----------|---------------|------------|
| M9: ToolSpec + Registry | 2 hr | 10h 30m |
| M10: InstrumentedGraph + StateMediator | 2 hr | 12h 30m |
| M11: PlanOrchestrator integration | 2.5 hr | 15h |
| M12: Prompt templates + LLM swap | 2.5 hr | 17h 30m |

These are working estimates. Phase 2 milestones take longer because they involve wiring existing infrastructure — you'll be reading and understanding the framework code as much as writing new code.

---

## Ready?

When you say "let's start M1," I'll provide:
1. The scaffolding files (state, tests, package init)
2. Clear instructions for what you write
3. Guidance when you get stuck
4. Verification that it works

Let's build.
