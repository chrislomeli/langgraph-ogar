# Plan Framework: Generic Plan Orchestration for Agentic Workflows

**Date:** 2026-02-17
**Status:** Core implemented, orchestrator complete
**Location:** `src/framework/langgraph_ext/planning/`

---

## Next Steps

| # | Task | Scope | Status | Notes |
|---|------|-------|--------|-------|
| 1 | Wire into music domain | `src/intent/plan_adapter.py` | **Done** | `bundle_to_plan_graph()` / `plan_graph_to_bundle()` converters, per-scope planners+executors, `music_registry()` factory. 13 tests in `tests/intent/test_plan_adapter.py`. |
| 2 | Wrap in LangGraph | `src/graph/` | Pending | Orchestrator logic inside graph nodes. `interrupt_before` for human review at approval gates. `Send()` for parallel execution of independent sub-plans. Checkpointing for persistence. |
| 3 | LLM scope detection | `src/graph/` | Pending | User says "make the chords jazzier" → LLM classifies `target_scopes={"harmony"}`. For small scope sets (5-8 types), a single LLM call with scope list in prompt suffices. RAG only needed if scope count grows large. |
| 4 | Plan persistence | `src/symbolic_music/persistence/` | Pending | Save/load `PlanGraph` to Memgraph. Content-addressed versioning of sub-plan content. Plan diffing for change review. |
| 5 | Executor retry policy | `orchestrator.py` | Pending | Configurable retry on `failed` sub-plans (max attempts, backoff). Currently fails once and stops. |

---

## Motivation

Most LLM agent frameworks provide tool calling, state management, and execution graphs — but no **plan management layer**. When an agent proposes complex, multi-step work, there's no structured way to:

- Represent the work as a reviewable, approvable plan
- Track dependencies between work items
- Propagate changes when one part of the plan is revised
- Run independent work items in parallel
- Maintain plan consistency across refinement cycles

This framework provides that layer. It is **domain-agnostic** — it knows nothing about music, code generation, data pipelines, or any specific application. Domain-specific content plugs in via typed sub-plans and registered executors.

### Analogy

Think of it as **Apache Airflow for LLM-proposed work**:

| Airflow | Plan Framework |
|---------|---------------|
| DAG of tasks | DAG of sub-plans |
| Scheduler (runs in a loop, manages task lifecycle) | Orchestrator (runs as a LangGraph cyclic graph, manages sub-plan lifecycle) |
| Operators (execute specific tasks) | Executors (domain agents/tools that act on approved sub-plans) |
| DAG definition (static Python code) | Plan schema (dynamic, LLM can propose structural changes) |

The orchestrator doesn't execute domain work — it **manages the plan** that describes the work.

---

## Architecture Overview

```
                          ┌─────────────────────────────┐
                          │      Plan Orchestrator       │
                          │   (LangGraph cyclic graph)   │
                          │                              │
                          │  propose → review → approve  │
                          │     ↑        ↓               │
                          │  refine ← execute → done     │
                          └──────────┬──────────────────┘
                                     │ manages
                                     ▼
                          ┌─────────────────────────────┐
                          │        Plan Graph            │
                          │     (DAG of SubPlans)        │
                          │                              │
                          │  [form] ──→ [harmony] ──┐    │
                          │  [voices]──→ [groove] ──┤    │
                          │              [render] ──┘    │
                          │                   ↓          │
                          │             [compile]        │
                          └─────────────────────────────┘
                                     │ dispatches to
                                     ▼
                          ┌─────────────────────────────┐
                          │    Domain Executors          │
                          │  (registered by application) │
                          │                              │
                          │  plan_harmony(), compile(),  │
                          │  render(), etc.              │
                          └─────────────────────────────┘
```

### Two graphs, different purposes

| | Plan Graph | Orchestrator Graph |
|---|---|---|
| **Model** | DAG (acyclic) | LangGraph graph (cyclic) |
| **What it represents** | Dependencies between work items | Control flow of plan management |
| **Cycles?** | No — enforced at construction | Yes — propose/review/refine loop |
| **Who defines it** | LLM + human (dynamic, mutable) | Framework (static code) |
| **Parallelism** | Independent branches run concurrently | Via LangGraph `Send()` |

---

## Plan Schema

### SubPlan

The atomic unit of planned work. Generic over content type `T`.

```python
class SubPlanStatus(str, Enum):
    """Lifecycle states for a sub-plan."""
    draft     = "draft"       # Proposed, not yet reviewed
    approved  = "approved"    # Human approved, ready for execution
    locked    = "locked"      # Approved + protected from invalidation
    stale     = "stale"       # Upstream dependency changed, needs re-planning
    executing = "executing"   # Currently being worked on
    done      = "done"        # Execution complete, result available
    failed    = "failed"      # Execution failed

class SubPlan(BaseModel, Generic[T]):
    """A single node in the plan DAG."""

    scope_id: str                          # Unique ID within the plan, e.g. "harmony", "compile"
    scope_type: str                        # Type tag for routing, e.g. "harmony_plan", "compilation"
    status: SubPlanStatus = SubPlanStatus.draft
    version: int = 1                       # Incremented on each re-plan

    content: Optional[T] = None            # Domain-specific payload (None until planned)
    result: Optional[Any] = None           # Execution result (None until done)

    condition: Optional[str] = None        # Optional: human-readable condition for inclusion
                                           # e.g. "only if groove.feel is latin"

    # Metadata
    created_at: datetime
    updated_at: datetime
    planned_by: Optional[str] = None       # Who/what produced the content ("deterministic_planner", "gpt-4", etc.)
```

### PlanGraph

The DAG of sub-plans with dependency edges.

```python
class PlanGraph(BaseModel):
    """
    A directed acyclic graph of sub-plans.

    Invariants:
    - No cycles (validated at construction and after every mutation)
    - Every dependency target exists
    - scope_ids are unique
    """

    plan_id: str
    title: str
    sub_plans: dict[str, SubPlan]                # scope_id → SubPlan
    dependencies: dict[str, set[str]]            # scope_id → set of scope_ids it depends on
    intent_summary: Optional[str] = None         # Original user intent (free text)

    # Lineage
    parent_plan_id: Optional[str] = None         # If this plan was refined from another
    version: int = 1
```

**Key operations on PlanGraph:**

```python
# --- Query ---
def roots(self) -> list[str]:
    """Sub-plans with no dependencies (can start immediately)."""

def leaves(self) -> list[str]:
    """Sub-plans with no dependents (terminal outputs)."""

def topological_order(self) -> list[str]:
    """All scope_ids in dependency order."""

def ready_to_execute(self) -> list[str]:
    """Sub-plans whose status is 'approved' and all dependencies are 'done'."""

def parallel_groups(self) -> list[set[str]]:
    """Groups of sub-plans that can execute concurrently (same topological level)."""

def downstream(self, scope_id: str) -> set[str]:
    """All transitive dependents of a sub-plan."""

def upstream(self, scope_id: str) -> set[str]:
    """All transitive dependencies of a sub-plan."""

# --- Mutation ---
def add_sub_plan(self, sub_plan: SubPlan, depends_on: set[str]) -> None:
    """Add a new sub-plan. Validates acyclicity."""

def remove_sub_plan(self, scope_id: str) -> None:
    """Remove a sub-plan and its edges. Validates no dangling refs."""

def add_dependency(self, from_id: str, to_id: str) -> None:
    """Add a dependency edge. Validates acyclicity."""

def update_content(self, scope_id: str, content: Any, planned_by: str) -> None:
    """Set sub-plan content, bump version, set status to draft."""
```

### Status Lifecycle

```
                    ┌──────────┐
          propose   │  draft   │◄──── re-plan (after stale)
                    └────┬─────┘
                         │ approve
                    ┌────▼─────┐
                    │ approved │
                    └────┬─────┘
                         │ execute          ┌────────┐
                    ┌────▼─────┐      ┌────►│ locked │ (opt-in, survives invalidation)
                    │executing │      │     └────────┘
                    └────┬─────┘      │
                    ┌────▼─────┐──────┘
                    │   done   │
                    └────┬─────┘
                         │ upstream changed
                    ┌────▼─────┐
                    │  stale   │──── re-plan ──→ draft
                    └──────────┘
```

**Transitions:**

| From | To | Trigger |
|------|----|---------|
| `draft` | `approved` | Human approval (or auto-approve policy) |
| `approved` | `executing` | Orchestrator dispatches to executor |
| `executing` | `done` | Executor returns result |
| `executing` | `failed` | Executor raises error |
| `done` | `stale` | Upstream dependency re-planned |
| `stale` | `draft` | Re-planning produces new content |
| `approved` | `locked` | Human explicitly locks |
| `locked` | `locked` | Upstream changes do NOT invalidate locked sub-plans |

---

## Orchestrator

The orchestrator is a **LangGraph cyclic graph** that manages the plan lifecycle. It is the "project manager" — it doesn't do domain work, it coordinates.

### Orchestrator Responsibilities

1. **Plan proposal** — Given user intent, produce an initial PlanGraph (delegate to a planner agent/function)
2. **Approval management** — Present sub-plans for review; collect approve/reject/revise decisions
3. **Execution dispatch** — For approved sub-plans with satisfied dependencies, dispatch to registered executors
4. **Parallel coordination** — Independent sub-plans execute concurrently (via LangGraph `Send()`)
5. **Invalidation propagation** — When a sub-plan is re-planned, walk the DAG downstream and mark dependents as stale
6. **Refinement routing** — Parse a refinement request, identify affected scopes, dispatch to the right planner
7. **Completion detection** — All leaves are `done` → plan is complete

### Orchestrator as a LangGraph Graph

```
                ┌──────────────────────────────────────────────┐
                │           Orchestrator Graph                  │
                │                                              │
   intent ──►  │  [propose] ──► [review] ──► [dispatch] ──┐   │
                │      ▲            │             │        │   │
                │      │         reject        execute     │   │
                │      │            │             │        │   │
                │      │            ▼             ▼        │   │
                │      │       [re-plan]    [wait/collect]  │   │
                │      │            │             │        │   │
                │      │            └─────────────┘        │   │
                │      │                  │                 │   │
                │      │            all done?               │   │
                │      │              │    │                │   │
                │      │          no  │    │ yes            │   │
                │      │              │    ▼                │   │
                │      │              │  [finish] ──────────┘   │
                │      │              │                         │
                │      └──── refinement request ◄──────────────┘
                │                                              │
                └──────────────────────────────────────────────┘
```

### Orchestrator State

```python
class OrchestratorState(TypedDict):
    """LangGraph state for the orchestrator."""

    # The plan being managed
    plan: PlanGraph

    # Current phase
    phase: Literal["proposing", "reviewing", "executing", "refining", "complete"]

    # Pending human decisions
    pending_approvals: list[str]           # scope_ids awaiting approval

    # Execution tracking
    executing: set[str]                    # scope_ids currently running
    completed_this_cycle: set[str]         # scope_ids completed in current dispatch round

    # Refinement
    refinement_request: Optional[RefinementRequest]

    # History
    messages: list[str]                    # Audit log of orchestrator decisions
```

### Orchestrator Nodes

```python
def propose_node(state: OrchestratorState) -> dict:
    """
    Given user intent, produce an initial PlanGraph.
    Delegates to a registered PlanProposer (LLM or rule-based).
    """

def review_node(state: OrchestratorState) -> dict:
    """
    Present draft sub-plans for human review.
    Uses interrupt_before for human-in-the-loop.
    Collects: approve / reject / lock decisions per scope_id.
    """

def dispatch_node(state: OrchestratorState) -> dict:
    """
    Find sub-plans that are approved + dependencies satisfied.
    Group into parallel batches.
    Dispatch to registered executors via Send().
    """

def collect_node(state: OrchestratorState) -> dict:
    """
    Collect execution results.
    Update sub-plan status to done/failed.
    Check if more sub-plans are now ready.
    """

def refine_node(state: OrchestratorState) -> dict:
    """
    Handle a refinement request:
    1. Identify affected scopes
    2. Re-plan those scopes (delegate to engine)
    3. Propagate invalidation downstream
    4. Return to review for re-approval
    """

def finish_node(state: OrchestratorState) -> dict:
    """All leaf sub-plans are done. Plan is complete."""
```

### Conditional Edges

```python
def route_after_review(state: OrchestratorState) -> str:
    """After review: dispatch if anything approved, or wait for more approvals."""
    if state["plan"].ready_to_execute():
        return "dispatch"
    if state["refinement_request"]:
        return "refine"
    return "review"  # wait for more human input

def route_after_collect(state: OrchestratorState) -> str:
    """After collecting results: more to dispatch, or refinement, or done."""
    plan = state["plan"]
    if plan.all_leaves_done():
        return "finish"
    if plan.ready_to_execute():
        return "dispatch"
    if any(sp.status == "stale" for sp in plan.sub_plans.values()):
        return "refine"
    return "review"  # need more approvals
```

---

## Invalidation Propagation

When a sub-plan is re-planned (new content), the orchestrator walks the DAG downstream:

```python
def propagate_invalidation(plan: PlanGraph, changed_scope_id: str) -> set[str]:
    """
    Mark all downstream sub-plans as stale (unless locked).
    Returns the set of scope_ids that were invalidated.
    """
    invalidated = set()
    for downstream_id in plan.downstream(changed_scope_id):
        sp = plan.sub_plans[downstream_id]
        if sp.status == SubPlanStatus.locked:
            continue  # locked sub-plans survive invalidation
        if sp.status in (SubPlanStatus.done, SubPlanStatus.approved, SubPlanStatus.executing):
            sp.status = SubPlanStatus.stale
            invalidated.add(downstream_id)
    return invalidated
```

This is the key mechanism that keeps the plan consistent. If the user says "change the harmony," the orchestrator:
1. Re-plans the harmony sub-plan → new content, status = draft
2. Propagates invalidation → compilation, rendering marked stale
3. Returns to review → user approves new harmony
4. Dispatches re-compilation → only affected voices recompile
5. Dispatches re-rendering → only stale sections re-render

---

## Refinement Routing

```python
class RefinementRequest(BaseModel):
    """A request to modify part of an existing plan."""

    prompt: str                            # What the user wants changed
    target_scopes: set[str] = set()        # Hint: which sub-plans are affected (empty = auto-detect)
    source_plan_id: Optional[str] = None   # The plan being refined
```

The orchestrator routes refinements:

1. **Scope detection** — If `target_scopes` is empty, the orchestrator (or an LLM) infers which sub-plans are affected by the prompt.
2. **Re-planning** — For each affected scope, dispatch to the registered planner for that scope type.
3. **Invalidation** — Propagate downstream from each re-planned scope.
4. **Review** — Return to the review node for approval of changes.

---

## Approval Policy

The orchestrator supports pluggable approval policies:

```python
class ApprovalPolicy(ABC):
    """Determines whether a sub-plan needs human approval."""

    @abstractmethod
    def needs_approval(self, sub_plan: SubPlan, context: PlanGraph) -> bool:
        """Return True if this sub-plan requires human sign-off."""

class AlwaysApprove(ApprovalPolicy):
    """Auto-approve everything (fully autonomous)."""
    def needs_approval(self, sub_plan, context):
        return False

class AlwaysReview(ApprovalPolicy):
    """Human reviews every sub-plan (maximum control)."""
    def needs_approval(self, sub_plan, context):
        return True

class ReviewStructuralChanges(ApprovalPolicy):
    """Auto-approve content changes; review structural changes (add/remove sub-plans)."""
    def needs_approval(self, sub_plan, context):
        return sub_plan.version == 1  # first version = new sub-plan = structural
```

---

## Domain Integration Points

The framework defines extension points. The domain (music, software, data pipelines, etc.) registers implementations.

### What the domain provides

```python
# 1. Sub-plan content types
#    These are the T in SubPlan[T]. Framework doesn't know their shape.
class HarmonyPlanContent(BaseModel): ...
class VoicePlanContent(BaseModel): ...
class CompilationResult(BaseModel): ...

# 2. Plan proposer — produces initial PlanGraph from user intent
class PlanProposer(ABC):
    @abstractmethod
    def propose(self, intent: str, context: dict) -> PlanGraph:
        """Turn user intent into a plan DAG."""

# 3. Sub-plan planners — produce content for a specific scope type
class SubPlanPlanner(ABC):
    @abstractmethod
    def plan(self, scope_type: str, context: PlanContext) -> Any:
        """Produce content for a sub-plan given the plan context."""

# 4. Executors — act on approved sub-plans
class SubPlanExecutor(ABC):
    @abstractmethod
    def execute(self, sub_plan: SubPlan, context: PlanContext) -> Any:
        """Execute an approved sub-plan, return result."""

# 5. Scope type registry — maps scope_type to engine + executor
class ScopeRegistry:
    def register(self, scope_type: str, planner: SubPlanPlanner, executor: SubPlanExecutor): ...
```

### Music domain registration (example)

```python
# In src/intent/ or src/graph/ — NOT in src/framework/
registry = ScopeRegistry()

registry.register(
    scope_type="voice_plan",
    planner=VoicePlanPlanner(),        # wraps DeterministicPlanner voice logic
    executor=NoOpExecutor(),           # voice plan doesn't "execute" — it's consumed by compilation
)

registry.register(
    scope_type="harmony_plan",
    planner=HarmonyPlanPlanner(),      # wraps DeterministicPlanner harmony logic
    executor=NoOpExecutor(),
)

registry.register(
    scope_type="compilation",
    planner=NoOpPlanner(),             # compilation doesn't need planning — it reads upstream sub-plans
    executor=PatternCompilerExecutor(),# wraps PatternCompiler.compile()
)

registry.register(
    scope_type="rendering",
    planner=NoOpPlanner(),
    executor=Music21RenderExecutor(),  # wraps render_composition()
)
```

### Music plan DAG (example)

```
  [voices] ────────────────────────────┐
  [form] ──────► [harmony] ──────┐     │
                 [groove] ───────┤     │
                                 ▼     ▼
                            [compilation]
                                 │
                                 ▼
                            [rendering]
```

Dependency declarations:
```python
dependencies = {
    "voices":      set(),                    # no dependencies (root)
    "form":        set(),                    # no dependencies (root)
    "harmony":     {"form"},                 # harmony needs form (section structure)
    "groove":      {"form"},                 # groove needs form (section structure)
    "compilation": {"voices", "harmony", "groove"},  # needs all upstream plans
    "rendering":   {"compilation"},          # needs compiled IR
}
```

---

## How It Maps to the Existing Codebase

### Current state (src/intent/)

```
Sketch ──► DeterministicPlanner.plan() ──► PlanBundle ──► PatternCompiler.compile() ──► CompileResult
                                               │
                                          PlanBundle is a monolithic artifact
                                          containing all sub-plans at once
```

### With the plan framework

```
Sketch ──► MusicPlanProposer.propose() ──► PlanGraph ──► Orchestrator ──► per-scope execution
                                               │
                                          PlanGraph is a DAG of SubPlans
                                          each managed independently
                                          with approval, invalidation, parallel execution
```

The existing `PlanBundle` sub-plans (`VoicePlan`, `FormPlan`, `HarmonyPlan`, `GroovePlan`, `RenderPlan`) become the **content types** of individual `SubPlan` nodes. The existing `DeterministicPlanner` logic is split into per-scope planners. The existing `PatternCompiler` becomes an executor registered for the `"compilation"` scope type.

---

## Proposed File Structure

```
src/framework/langgraph_ext/planning/
    __init__.py                    # Barrel exports
    models.py                      # SubPlan, SubPlanStatus, PlanGraph, RefinementRequest
    dag.py                         # DAG operations: topological sort, cycle detection,
                                   #   parallel groups, invalidation propagation
    orchestrator.py                # Orchestrator LangGraph graph definition
    registry.py                    # ScopeRegistry, PlanProposer ABC, SubPlanPlanner ABC,
                                   #   SubPlanExecutor ABC
    approval.py                    # ApprovalPolicy ABC + built-in policies

tests/framework/
    test_plan_dag.py               # DAG operations, cycle detection, invalidation
    test_plan_models.py            # SubPlan lifecycle, PlanGraph validation
    test_orchestrator.py           # Orchestrator state machine, routing
    test_approval.py               # Approval policies
```

---

## Design Principles

1. **Framework knows nothing about music.** All domain knowledge lives in registered content types, planners, and executors.

2. **The plan is the source of truth.** The orchestrator never bypasses the plan. Every action is reflected in sub-plan status changes.

3. **DAG for the plan, cycles for the orchestrator.** The plan dependency graph is acyclic (enforced). The orchestrator execution graph has cycles (propose/review/refine loop).

4. **Invalidation is automatic, re-approval is required.** When upstream changes, downstream is marked stale. The orchestrator doesn't silently re-execute — it routes back through review (unless auto-approve policy is active).

5. **Locked means locked.** A locked sub-plan survives upstream invalidation. This is the user saying "I like this, don't touch it."

6. **Dynamic DAGs.** The LLM can propose structural changes to the plan (add/remove sub-plans, change dependencies). The framework validates acyclicity after every mutation.

7. **Parallel by default.** Independent branches of the DAG execute concurrently. The orchestrator uses topological grouping to maximize parallelism.

---

## Open Questions

1. **Granularity of sub-plans.** Should "compilation" be one sub-plan, or one per voice? Finer granularity enables more targeted regeneration but increases orchestrator complexity. The music domain's `CompileOptions.regenerate_voices` suggests per-voice compilation sub-plans may be valuable.

2. **Plan persistence.** Should PlanGraphs be persisted to Memgraph alongside compositions? This enables plan history, diffing, and rollback. The lineage edges (`REFINED_FROM`, `PLANNED_AS`) from `ARCHITECTURE_OVERVIEW.md` suggest yes.

3. **LLM scope detection.** When a refinement request doesn't specify target scopes, how does the orchestrator infer them? Options: keyword matching (like the current `DeterministicPlanner.refine()`), LLM classification, or always ask the user.

4. **Executor error handling.** When an executor fails, should the sub-plan go to `failed` and stop, or should the orchestrator retry? Configurable retry policy per scope type?

5. **Plan diffing.** When a sub-plan is re-planned, should the framework compute a diff between old and new content? This would help the user understand what changed during review. Requires domain-specific diff logic (or generic JSON diff as a fallback).
