# OGAR Session Progress & Next Assignments

**Last updated:** Mar 7, 2026

---

## What We Built

### 1. Outer OGAR Graph (`src/ogar/runtime/graph/ogar_graph.py`)

Full 7-node orchestration graph with conditional routing:

```
START → intake → planner → tool_select → execute → verify → decide
                                                              ↓
                                                tool_select ← (next step)
                                                planner    ← (revise plan)
                                                finalize   → END
```

- **intake** — modular subgraph (goals + requirements elicitation)
- **planner** — wired to real PlanOrchestrator (DAG lifecycle)
- **tool_select** — stub (reads current plan step)
- **execute** — stub (canned success)
- **verify** — stub (accepts everything)
- **decide** — router node (next_step / revise_plan / done / fail)
- **finalize** — marks run done, appends to audit log

State: `OGARState` TypedDict with identity, domain, intake, planning, tool execution, and control fields.

### 2. Intake Subgraph (`src/ogar/runtime/graph/intake/`)

Modular LangGraph subgraph for goals + requirements elicitation:

```
START → control → [done?] → END
                → consult → apply_and_validate → control (loop)
```

- `control` — loads/creates project, determines next stage, generates questions
- `consult` — calls `ask_human` + `call_ai` (both injectable via Protocol)
- `apply_and_validate` — applies ProjectPatch, validates, saves

### 3. Three CallAI Implementations

All match the same `CallAI` Protocol — swap with one argument:

| Implementation | File | Tools? | LLM? |
|---|---|---|---|
| **Stub** | `domain/consult/call_the_ai.py` | ❌ | ❌ |
| **Structured LLM** | `domain/consult/call_the_ai_llm.py` | ❌ | ✅ GPT-4o-mini |
| **ReAct agent** | `domain/consult/call_the_ai_react.py` | ✅ | ✅ GPT-4o-mini |

```python
graph = build_intake_graph(call_ai=call_the_ai)        # stub
graph = build_intake_graph(call_ai=call_the_ai_llm)    # LLM only
graph = build_intake_graph(call_ai=call_the_ai_react)  # ReAct (LLM + tools)
```

The ReAct agent has 2 stub tools:
- `count_goals` — counts goals in the project
- `check_goal_requirements_coverage` — reports which goals lack requirements

### 4. PlanOrchestrator Integration (`domain/services/plan_proposer.py`, `plan_executors.py`)

- **ProjectPlanProposer** — builds a PlanGraph DAG from the Project:
  ```
  work_g_1 ─┐
  work_g_2 ─┼── validate ── report
  ```
- **Stub executors** for each scope type (`goal_work`, `validate`, `report`)
- **FaultMode enum** for testing failure scenarios:
  - `FaultMode.none` — always succeed
  - `FaultMode.transient` — fail N times, then succeed
  - `FaultMode.permanent` — always fail
  - `FaultMode.timeout` — raises TimeoutError

```python
from ogar.domain.services.plan_executors import build_fault_registry, FaultMode
graph = build_ogar_graph(registry=build_fault_registry(FaultMode.transient, 2))
```

### 5. Test Suite (35 tests, <0.2s)

| File | Count | Covers |
|---|---|---|
| `tests/ogar/test_intake.py` | 8 | Intake happy path + edge cases |
| `tests/ogar/test_planner.py` | 15 | Proposer DAG, orchestrator, faults |
| `tests/ogar/test_ogar_pipeline.py` | 12 | Full pipeline + decide routing |

### 6. Tool Contract Framework (`src/ogar/adapters/tools/`)

Already in the repo from earlier work. Well-designed, MCP-ready:

- **ToolSpec** — immutable definition (name, Pydantic input/output, handler)
- **ToolRegistry** — catalog with JSON Schema export
- **ToolResultEnvelope** — provenance metadata (timing, hash, error classification)
- **LocalToolClient** — 3-phase validation (input → execute → output)

Not yet wired into the OGAR graph — that's Assignment 2 below.

---

## Run Commands

```bash
# Intake only
python -m ogar.scripts.run_intake          # stubs, instant
python -m ogar.scripts.run_intake_llm      # LLM, ~5s
python -m ogar.scripts.run_intake_react    # ReAct + tools, ~10s

# Full pipeline
python -m ogar.scripts.run_ogar            # stubs, instant

# Tests
python -m pytest tests/ogar/ -v            # 35 tests, <0.2s
```

---

## File Layout

```
src/ogar/
├── adapters/
│   ├── persistence/            # ProjectStore (JSON file)
│   └── tools/                  # ToolSpec, ToolRegistry, LocalToolClient, Envelope
├── domain/
│   ├── consult/
│   │   ├── __init__.py         # AskHuman + CallAI Protocols
│   │   ├── ask_the_human.py    # Stub human interaction
│   │   ├── call_the_ai.py      # Stub AI (deterministic)
│   │   ├── call_the_ai_llm.py  # LLM structured output
│   │   ├── call_the_ai_react.py # ReAct agent (LLM + tools)
│   │   ├── patches.py          # ProjectPatch model
│   │   └── apply_patch.py      # Apply patch to Project
│   ├── models/
│   │   └── project.py          # Project, Goal, Requirement, Uncertainty, WorkItem
│   └── services/
│       ├── plan_executors.py   # Stub executors + FaultMode + build_fault_registry()
│       ├── plan_proposer.py    # ProjectPlanProposer (Project → PlanGraph)
│       ├── progression.py      # Stage progression logic
│       ├── questions.py        # Blocking questions per stage
│       ├── project_validate.py # Validation
│       └── reports.py          # Uncertainty reports
├── planning/                   # PlanOrchestrator, ScopeRegistry, PlanGraph, DAG, Approval
├── runtime/
│   ├── graph/
│   │   ├── __init__.py         # Exports build_ogar_graph + build_intake_graph
│   │   ├── ogar_graph.py       # Outer graph (7 nodes)
│   │   └── intake/
│   │       ├── __init__.py
│   │       └── graph_builder.py
│   └── sidecars/               # Interceptors, middleware (not yet wired)
└── scripts/
    ├── run_intake.py
    ├── run_intake_llm.py
    ├── run_intake_react.py
    └── run_ogar.py
```

---

## Your Next Assignments

Work through these in order. Each builds on the previous one.

### Assignment 1: Wire ToolClient into the Execute Node ⭐ (highest priority)

**Goal:** Replace the execute stub with real tool dispatch using your `LocalToolClient`.

**Steps:**
1. Create 2-3 real tool handlers as `ToolSpec` objects (e.g. `validate_project`, `report_uncertainties`). Put them in `src/ogar/domain/services/tools/`.
2. Register them in a `ToolRegistry`.
3. In `ogar_graph.py`, replace the `execute` stub:
   - It currently returns canned `{"success": True}`.
   - Instead: `client = LocalToolClient(registry)` → `envelope = client.call(tool_name, args)` → return `tool_response` from the envelope.
4. Update the `verify` node to inspect `envelope.meta.success` and `envelope.meta.error` to classify failures.
5. Add tests in `tests/ogar/test_execute.py`.

**What you learn:** How your ToolSpec contract framework integrates with the graph. The three error types (`input_validation_error`, `execution_error`, `output_validation_error`) map directly to the decide node's routing.

### Assignment 2: Bridge ToolSpec → LangChain @tool

**Goal:** Write a utility that converts your `ToolSpec` objects into LangChain `@tool` functions so the ReAct agent can use them.

**Steps:**
1. In `src/ogar/adapters/tools/`, create `langchain_bridge.py`.
2. Write `def toolspec_to_langchain(spec: ToolSpec) -> BaseTool` that wraps `spec.handler` in a LangChain tool.
3. Update `call_the_ai_react.py` to use this bridge instead of the hand-written `@tool` functions.
4. This means one tool definition (`ToolSpec`) powers both the execute node AND the ReAct agent.

**What you learn:** How framework abstractions compose. One tool definition, two consumers.

### Assignment 3: Add the "design" Stage to Intake

**Goal:** Extend the intake loop beyond goals + requirements.

**Steps:**
1. In `progression.py`, add `"design"` between requirements and done.
2. In `questions.py`, add blocking questions for the design stage.
3. In `call_the_ai.py`, add `_mock_design_patch` returning design decisions.
4. Update `call_the_ai_llm.py` with a `DESIGN_SYSTEM_PROMPT`.
5. Update tests to expect the new stage.

**What you learn:** How adding a new stage flows through the entire system — progression, questions, AI, patch, validation.

### Assignment 4: Evaluation Harness (15% of rubric)

**Goal:** Build a systematic way to evaluate the pipeline's behavior.

**Steps:**
1. Create `tests/ogar/test_evaluation.py`.
2. Define 3-5 "scenarios" as fixtures: happy path, fault injection, empty project, many goals, conflicting requirements.
3. For each scenario, assert on: final state, audit log completeness, error handling behavior, timing.
4. Consider using `FaultMode` to test graceful degradation.
5. Optional: output a JSON "evaluation report" for each scenario.

**What you learn:** How to systematically verify agent behavior — the hardest rubric item.

### Assignment 5: Observability via Sidecars

**Goal:** Wire the existing interceptor/middleware code (`runtime/sidecars/`) into the graph.

**Steps:**
1. Read `runtime/sidecars/interceptors/logging_interceptor.py` and `metrics_interceptor.py`.
2. Read `runtime/sidecars/middleware/state_mediator.py`.
3. Wire a logging interceptor into the graph so every node transition is logged.
4. Wire metrics so you can see per-node timing.

**What you learn:** How observability works in a graph-based system. This is the "instrumentation" part of the rubric.

---

## Key Design Patterns to Study

1. **Protocol injection** — `CallAI` and `AskHuman` are Protocols. Swap implementations without changing the graph. See `domain/consult/__init__.py`.

2. **Factory nodes** — `_build_intake_node()` and `_make_planner_node()` are factories that capture dependencies via closure. The graph only sees a plain function.

3. **Envelope pattern** — `ToolResultEnvelope` wraps every tool result with provenance metadata. The tool handler stays pure; the client adds the envelope. See `adapters/tools/envelope.py`.

4. **Fault injection via composition** — `FaultMode` + `build_fault_registry()` lets you test failure paths without changing production code. See `domain/services/plan_executors.py`.

5. **DAG-driven execution** — `PlanOrchestrator` respects dependency edges. `validate` won't run until all `goal_work` sub-plans finish. See `planning/orchestrator.py`.

---

## API Keys

Loaded from `~/Source/SECRETS/.env` via python-dotenv. Required for LLM/ReAct scripts only.
Stub scripts and tests need no API key.
