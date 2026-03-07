# Planner Specification
## Role: Structured Context Compiler

---

# 1. Purpose

The Planner exists to:

- Maintain a structured representation of the objective and progress.
- Provide consistent, bounded, structured context to the LLM.
- Track plan revisions and step status over time.
- Preserve traceability between decisions, evidence, and outcomes.

The Planner does **not** execute work.

It does not call tools.  
It does not control workflow.  
It does not retry.  
It does not branch.  
It does not schedule.  

All orchestration belongs to the graph runtime.

---

# 2. Planner Responsibilities

The Planner is responsible for:

1. Maintaining the canonical plan structure.
2. Recording progress and evidence.
3. Producing a structured “Briefing” for LLM reasoning.
4. Tracking plan revisions and rationale.
5. Enforcing valid state transitions for steps.
6. Ensuring traceability between steps and supporting evidence.

---

# 3. Planner Non-Responsibilities

The Planner must never:

- Decide what happens next.
- Call tools directly.
- Retry operations.
- Manage concurrency.
- Mutate external or global state.
- Store checkpoint history.
- Embed branching logic.
- Perform execution-time scheduling.

It is a structured state transformer only.

---

# 4. Plan Model

## 4.1 Plan

- `plan_version: int`
- `objective: str`
- `constraints: list[str]`
- `acceptance_criteria: list[str]`
- `steps: list[Step]`
- `revision_history: list[PlanRevision]`
- `open_questions: list[str]`
- `decisions: list[DecisionRecord]`

---

## 4.2 Step

Each step must be descriptive, not executable.

- `step_id: str`
- `title: str`
- `intent: str`
- `inputs_needed: list[str]`
- `expected_outputs: list[str]`
- `done_definition: str`
- `risk_level: str`
- `status: enum(todo | in_progress | blocked | done | failed)`
- `evidence_refs: list[str]`
- `notes: list[str]`

Optional:

- `suggested_capabilities: list[str]`
  - Non-binding hints such as `"search"`, `"read"`, `"compute"`

Forbidden:

- Tool names
- Tool arguments
- Retry policies
- Control-flow instructions

---

## 4.3 PlanRevision

- `revision_id: str`
- `timestamp: datetime`
- `rationale: str`
- `delta_summary: str`

Each revision must increment `plan_version`.

---

## 4.4 DecisionRecord

- `decision_id: str`
- `timestamp: datetime`
- `decision: str`
- `rationale: str`
- `evidence_refs: list[str]`

---

# 5. Allowed Planner Operations

The Planner may expose the following methods:

- `create_plan(objective, constraints)`
- `revise_plan(new_steps, rationale)`
- `mark_step_done(step_id, evidence_refs)`
- `mark_step_blocked(step_id, reason)`
- `mark_step_failed(step_id, reason)`
- `record_decision(text, rationale, evidence_refs)`
- `add_open_question(question)`
- `generate_briefing()`

The Planner must not decide when these methods are called.

It may validate transitions but not initiate them.

---

# 6. Briefing Format

The Planner produces a structured briefing object for LLM reasoning.

## 6.1 Briefing Structure

The briefing must include:

1. Objective Summary
2. Constraints
3. Acceptance Criteria
4. Plan Overview (step titles + statuses)
5. Current Step Focus
6. Known Facts (referenced via evidence IDs)
7. Open Questions
8. Recent Decisions
9. Policy or Safety Reminders (if applicable)

---

## 6.2 Briefing Requirements

The briefing must:

- Have a stable structure across runs.
- Avoid dumping raw state.
- Reference evidence by ID rather than duplicating tool outputs.
- Be compact and token-efficient.
- Be deterministic given state.

---

# 7. Versioning & Traceability

- Every plan revision increments `plan_version`.
- Revision history must record rationale.
- Step transitions must be valid (no illegal transitions).
- Evidence references must correspond to recorded tool results.
- Decision records must cite supporting evidence.

The Planner is responsible for enforcing internal consistency.

---

# 8. Boundary Rule

The Planner describes work.

The Graph decides when to perform it.

The Tools perform it.

The Planner never crosses these boundaries.

---

# 9. Design Principles

- Deterministic state transformations
- Explicit traceability
- No hidden control logic
- Stable interfaces
- Separation of reasoning and execution
- Portability across projects

---

End of Specification