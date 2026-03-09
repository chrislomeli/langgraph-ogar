"""
ogar_graph — the outer orchestration graph.

Topology (declarative)
----------------------
    START → intake
    intake → planner
    planner → tool_select
    tool_select → execute
    execute → verify
    verify → decide
    decide → planner        (plan revision needed)
    decide → tool_select    (next step in plan)
    decide → finalize       (all steps done or budget exhausted)
    finalize → END

Each phase is either:
  - A subgraph (intake, planner, execute) — has its own internal loop
  - A node (tool_select, verify, decide, finalize) — single pass

Subgraphs are compiled separately and wired in as nodes.
The outer graph only sees their input/output state boundaries.

Design decisions
----------------
- Intake is a subgraph because it loops (control→consult→validate).
- Planner will be a subgraph when it gets a draft→approve→revise loop.
- Execute will be a subgraph when it gets a call→verify→retry loop.
- tool_select, verify, decide, finalize are thin nodes (policy checks, routing).
- State flows through OGARState, which is the superset.
  Subgraphs read/write only their slice of it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

from ogar.domain.models.project import Project
from ogar.domain.consult import AskHuman, CallAI
from ogar.commons.results import NodeResult, validated_node, handle_error


# ── Input schemas (Pydantic, extra="ignore") ─────────────────────────

class PlannerInput(BaseModel):
    model_config = {"extra": "ignore", "arbitrary_types_allowed": True}
    project: Optional[Project] = None
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)


class ToolSelectInput(BaseModel):
    model_config = {"extra": "ignore"}
    plan_steps: List[Dict[str, Any]] = Field(default_factory=list)
    current_step_index: int = 0


class ExecuteInput(BaseModel):
    model_config = {"extra": "ignore"}
    tool_request: Optional[Dict[str, Any]] = None
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)


class VerifyInput(BaseModel):
    model_config = {"extra": "ignore"}
    tool_response: Optional[Dict[str, Any]] = None
    plan_steps: List[Dict[str, Any]] = Field(default_factory=list)
    current_step_index: int = 0


class DecideInput(BaseModel):
    model_config = {"extra": "ignore"}
    plan_steps: List[Dict[str, Any]] = Field(default_factory=list)
    current_step_index: int = 0
    tool_error: Optional[str] = None
    retry_count: int = 0


class FinalizeInput(BaseModel):
    model_config = {"extra": "ignore"}
    decision: str = "done"
    audit_log: List[Dict[str, Any]] = Field(default_factory=list)


# ── State ────────────────────────────────────────────────────────────

class OGARState(TypedDict):
    # ── Identity ──
    pid: str

    # ── Domain state (flows through the whole run) ──
    project: Optional[Project]

    # ── Intake phase ──
    stage: str                                # intake sub-stage: goals, requirements, done
    questions: List[str]
    human_reply: Optional[str]
    patch: Optional[Dict[str, Any]]
    validation_errors: List[str]

    # ── Planning phase ──
    plan_steps: List[Dict[str, Any]]          # ordered steps the planner produced
    current_step_index: int                    # which step we're executing

    # ── Tool execution phase ──
    tool_request: Optional[Dict[str, Any]]    # what to call (tool_name, args)
    tool_response: Optional[Dict[str, Any]]   # what came back (envelope)
    tool_error: Optional[str]                 # error message if failed
    retry_count: int                          # retries for current step

    # ── Control ──
    run_status: str                           # "running", "done", "failed"
    audit_log: List[Dict[str, Any]]           # append-only event log

    # ── Decision routing ──
    decision: str                             # "next_step", "revise_plan", "done", "fail"

    # ── Validation ──
    node_result: Optional[NodeResult]


# ── Intake (subgraph) ───────────────────────────────────────────────

def _build_intake_node(ask_human=None, call_ai=None):
    """Compile the intake subgraph and return it as a callable node."""
    from ogar.runtime.graph.intake import build_intake_graph
    kwargs = {}
    if ask_human is not None:
        kwargs["ask_human"] = ask_human
    if call_ai is not None:
        kwargs["call_ai"] = call_ai
    return build_intake_graph(**kwargs)


# ── Planner (wired to PlanOrchestrator) ──────────────────────────────

def  _make_planner_node(registry=None):
    """
    Factory: return a planner node, optionally with a custom ScopeRegistry.

    Pass a fault-injected registry to test failure scenarios:
        from ogar.domain.services.plan_executors import build_fault_registry, FaultMode
        registry = build_fault_registry(FaultMode.transient, 2)
        graph = build_ogar_graph(registry=registry)
    """

    @validated_node(PlannerInput)
    def planner(inp: PlannerInput, state: dict) -> dict:
        """
        Produce and execute a plan from the project's goals and requirements.

        Uses the real PlanOrchestrator:
          1. ProjectPlanProposer builds a PlanGraph (DAG of sub-plans)
          2. PlanOrchestrator.run() drives the lifecycle:
             auto-approve → execute → done (per sub-plan)
          3. Results are converted to plan_steps for the outer graph.
        """
        from ogar.planning.orchestrator import PlanOrchestrator, OrchestratorEvent
        from ogar.domain.services.plan_proposer import ProjectPlanProposer
        from ogar.domain.services.plan_executors import build_default_registry

        project = inp.project
        audit = list(inp.audit_log)

        if not project or not project.goals:
            return {
                "plan_steps": [],
                "current_step_index": 0,
                "run_status": "running",
                "audit_log": audit + [{"event": "plan_skipped", "reason": "no goals"}],
                "node_result": NodeResult.success(),
            }

        # Collect orchestrator events into the audit log
        def on_event(event: OrchestratorEvent):
            audit.append({
                "event": f"orch_{event.kind.value}",
                "scope_id": event.scope_id,
                "detail": event.detail,
            })

        # Use injected registry or default
        reg = registry if registry is not None else build_default_registry()
        proposer = ProjectPlanProposer()
        orchestrator = PlanOrchestrator(
            registry=reg,
            proposer=proposer,
            on_event=on_event,
        )

        # Propose a plan from the project
        plan = orchestrator.propose(
            intent=f"Execute plan for project: {project.title}",
            context={"project": project},
        )

        # Run to completion (AlwaysApprove is the default policy)
        result = orchestrator.run()

        # Convert PlanGraph sub-plans → plan_steps for the outer graph
        steps = []
        for scope_id, sp in plan.sub_plans.items():
            steps.append({
                "step_id": scope_id,
                "title": f"[{sp.scope_type}] {scope_id}",
                "tool": sp.scope_type,
                "args": sp.content or {},
                "status": sp.status.value,
                "result": sp.result,
            })

        return {
            "plan_steps": steps,
            "current_step_index": len(steps),  # all steps already executed
            "run_status": "running",
            "audit_log": audit,
            "node_result": NodeResult.success(),
        }

    return planner


# ── Tool selection / gating (stub) ──────────────────────────────────

@validated_node(ToolSelectInput)
def tool_select(inp: ToolSelectInput, state: dict) -> dict:
    """
    Pick the next tool call based on current plan step.
    Apply gating policies (risk, budget, environment).

    STUB: just reads the current step and passes it through.

    In production:
      - Checks ApprovalPolicy
      - Checks budget remaining
      - Checks risk level of the tool
      - May block the call and route to human approval
    """
    if inp.current_step_index >= len(inp.plan_steps):
        return {"tool_request": None, "decision": "done", "node_result": NodeResult.success()}

    step = inp.plan_steps[inp.current_step_index]
    return {
        "tool_request": {
            "tool_name": step["tool"],
            "args": step["args"],
            "step_id": step["step_id"],
        },
        "tool_error": None,
        "retry_count": 0,
        "node_result": NodeResult.success(),
    }


# ── Execute (stub) ──────────────────────────────────────────────────

@validated_node(ExecuteInput)
def execute(inp: ExecuteInput, state: dict) -> dict:
    """
    Call the selected tool and capture the response.

    STUB: returns a canned success response.

    In production this is a subgraph:
      call_tool → verify_output → retry_or_done
    Uses ToolClient from ogar.adapters.tools for:
      - Schema validation
      - ToolResultEnvelope wrapping
      - Error classification (transient vs permanent)
      - Bounded retries
    """
    req = inp.tool_request
    if req is None:
        return {"tool_response": None, "node_result": NodeResult.success()}

    # STUB: pretend every tool call succeeds
    return {
        "tool_response": {
            "tool_name": req["tool_name"],
            "step_id": req["step_id"],
            "success": True,
            "result": f"Stub result for {req['tool_name']}",
        },
        "tool_error": None,
        "audit_log": list(inp.audit_log) + [
            {"event": "tool_executed", "tool": req["tool_name"], "success": True}
        ],
        "node_result": NodeResult.success(),
    }


# ── Verify (stub) ───────────────────────────────────────────────────

@validated_node(VerifyInput)
def verify(inp: VerifyInput, state: dict) -> dict:
    """
    Check the tool response against expectations.

    STUB: accepts everything.

    In production:
      - Validates output schema
      - Checks for partial results
      - Classifies errors (transient → retry, permanent → fail)
      - Updates step status
    """
    resp = inp.tool_response
    if resp and resp.get("success"):
        # Mark current step done
        steps = list(inp.plan_steps)
        idx = inp.current_step_index
        if idx < len(steps):
            steps[idx] = {**steps[idx], "status": "done"}
        return {"plan_steps": steps, "node_result": NodeResult.success()}

    return {"node_result": NodeResult.success()}


# ── Decide (router node) ────────────────────────────────────────────

@validated_node(DecideInput)
def decide(inp: DecideInput, state: dict) -> dict:
    """
    Look at where we are in the plan and decide what's next.

    Returns a 'decision' field that the router reads:
      - "next_step"    → advance index, go back to tool_select
      - "revise_plan"  → something failed, go back to planner
      - "done"         → all steps complete, go to finalize
      - "fail"         → budget/retries exhausted, go to finalize
    """
    # If error and too many retries → fail
    if inp.tool_error and inp.retry_count >= 3:
        return {"decision": "fail", "run_status": "failed", "node_result": NodeResult.success()}

    # If error → revise plan (in production, could retry first)
    if inp.tool_error:
        return {"decision": "revise_plan", "node_result": NodeResult.success()}

    # If all steps done → done
    all_done = all(s.get("status") == "done" for s in inp.plan_steps) if inp.plan_steps else True
    if inp.current_step_index >= len(inp.plan_steps) or (inp.current_step_index >= len(inp.plan_steps) - 1 and all_done):
        return {"decision": "done", "node_result": NodeResult.success()}

    # Otherwise → next step
    return {
        "decision": "next_step",
        "current_step_index": inp.current_step_index + 1,
        "node_result": NodeResult.success(),
    }


# ── Finalize ─────────────────────────────────────────────────────────

@validated_node(FinalizeInput)
def finalize(inp: FinalizeInput, state: dict) -> dict:
    """
    Wrap up the run. Produce summary, save final state.

    STUB: just marks the run as done.

    In production:
      - Generates run summary report
      - Persists final project state
      - Emits observability events
      - Produces audit trail
    """
    status = "done" if inp.decision == "done" else "failed"
    return {
        "run_status": status,
        "audit_log": list(inp.audit_log) + [
            {"event": "run_finalized", "status": status}
        ],
        "node_result": NodeResult.success(),
    }


# ── Router ───────────────────────────────────────────────────────────

def _route_after_node(state: OGARState) -> str:
    """Check node_result first — route to handle_error on failure."""
    result = state.get("node_result")
    if result and not result.ok:
        return "handle_error"
    return "continue"


def _route_after_decide(state: OGARState) -> str:
    """Route based on the decide node's decision field."""
    d = state.get("decision", "done")
    if d == "next_step":
        return "tool_select"
    if d == "revise_plan":
        return "planner"
    return "finalize"  # "done" or "fail"


# ── Build ────────────────────────────────────────────────────────────

def build_ogar_graph(
    ask_human: AskHuman | None = None,
    call_ai: CallAI | None = None,
    registry=None,
):
    """
    Build the full OGAR orchestration graph.

    Parameters
    ----------
    ask_human : AskHuman, optional
        Override for human interaction in the intake subgraph.
    call_ai : CallAI, optional
        Override for AI generation in the intake subgraph.
        Pass call_the_ai_llm here to use the real LLM.
    registry : ScopeRegistry, optional
        Override for the planner's ScopeRegistry.
        Pass build_fault_registry(...) to inject faults for testing.

    Topology
    --------
        START → intake → planner → tool_select → execute → verify → decide
        decide → tool_select    (next step)
        decide → planner        (revise plan)
        decide → finalize → END
    """
    g = StateGraph(OGARState)

    # ── Nodes ──
    g.add_node("intake", _build_intake_node(ask_human, call_ai))
    g.add_node("planner", _make_planner_node(registry))
    g.add_node("tool_select", tool_select)
    g.add_node("execute", execute)
    g.add_node("verify", verify)
    g.add_node("decide", decide)
    g.add_node("finalize", finalize)
    g.add_node("handle_error", handle_error)

    # ── Edges — standard routing checks node_result after each node ──
    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", _route_after_node,
                            {"continue": "planner", "handle_error": "handle_error"})
    g.add_conditional_edges("planner", _route_after_node,
                            {"continue": "tool_select", "handle_error": "handle_error"})
    g.add_conditional_edges("tool_select", _route_after_node,
                            {"continue": "execute", "handle_error": "handle_error"})
    g.add_conditional_edges("execute", _route_after_node,
                            {"continue": "verify", "handle_error": "handle_error"})
    g.add_conditional_edges("verify", _route_after_node,
                            {"continue": "decide", "handle_error": "handle_error"})
    g.add_conditional_edges("decide", _route_after_decide,
                            ["tool_select", "planner", "finalize"])
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()
