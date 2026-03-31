"""
graph_builder — the intake graph.

Topology (declarative)
----------------------
    START → control
    control → END          (stage == "done")
    control → consult      (otherwise)
    consult → apply_and_validate
    apply_and_validate → consult   (validation errors)
    apply_and_validate → control   (no errors — next stage)

Nodes do computation and return state updates (plain dicts).
Routing decisions live in router functions, declared as conditional edges.
The graph topology is fully visible in build_graph().

Stubs
-----
ask_the_human  and  call_the_ai  are the only two pieces to swap.
Pass different implementations to build_graph() via the Protocol interface.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

from ogar.domain.models.project import Project
from ogar.domain.services.progression import determine_next_stage
from ogar.domain.services.questions import blocking_questions_for_stage
from ogar.domain.services.project_validate import validate_project
from ogar.adapters.persistence.project_store import JsonFileProjectStore
from ogar.domain.consult.patches import ProjectPatch
from ogar.domain.consult.apply_patch import apply_patch
from ogar.domain.consult import AskHuman, CallAI
from ogar.domain.consult.ask_the_human import ask_the_human as default_ask_human
from ogar.domain.consult.call_the_ai import call_the_ai as default_call_ai
from ogar.commons.results import NodeResult, validated_node, handle_error

STORE = JsonFileProjectStore("./data")


# ── Input schemas (Pydantic, extra="ignore") ─────────────────────────

class ControlInput(BaseModel):
    model_config = {"extra": "ignore", "arbitrary_types_allowed": True}
    pid: str
    project: Optional[Project] = None


class ConsultInput(BaseModel):
    model_config = {"extra": "ignore", "arbitrary_types_allowed": True}
    stage: str
    questions: List[str] = Field(default_factory=list)
    project: Project


class ApplyAndValidateInput(BaseModel):
    model_config = {"extra": "ignore", "arbitrary_types_allowed": True}
    project: Project
    patch: Dict[str, Any]


# ── State ────────────────────────────────────────────────────────────
class IntakeState(TypedDict):
    pid: str
    project: Optional[Project]
    stage: str
    questions: List[str]
    human_reply: Optional[str]          # free text from the human
    patch: Optional[Dict[str, Any]]     # serialised ProjectPatch from the AI
    validation_errors: List[str]
    node_result: Optional[NodeResult]


# ── Node 1: control ──────────────────────────────────────────────────
@validated_node(ControlInput)
def control(inp: ControlInput, state: dict) -> dict:
    """Load/create project, decide next stage, generate questions."""

    # Load or create
    project = inp.project
    if project is None:
        try:
            project = STORE.load_project(inp.pid)
        except FileNotFoundError:
            project = Project(pid=inp.pid, title="")

    # Decide next stage
    stage = determine_next_stage(project)

    # Build the questions for this stage (empty if done)
    questions = blocking_questions_for_stage(project, stage) if stage != "done" else []

    return {
        "project": project,
        "stage": stage,
        "questions": questions,
        "node_result": NodeResult.success(),
    }


# ── Node 2: consult (factory) ────────────────────────────────────────
def _make_consult_node(ask_human: AskHuman, call_ai: CallAI):
    """Return a consult node wired to the given implementations."""

    @validated_node(ConsultInput)
    def consult(inp: ConsultInput, state: dict) -> dict:
        """
        Two calls:
          1. ask_human()  — get free-text input   (stub: canned reply)
          2. call_ai()    — parse into a patch     (stub: deterministic mock)

        In production:
          - ask_human is your chat UI / CLI
          - call_ai is an LLM call (or ReAct agent) that may loop with
            the human until it has an actionable response
        """
        # 1. Human interaction
        human_reply = ask_human(inp.stage, inp.questions)

        # 2. AI produces a structured patch from the human's reply
        patch: ProjectPatch = call_ai(inp.project, inp.stage, human_reply)

        return {
            "human_reply": human_reply,
            "patch": patch.model_dump(),
            "node_result": NodeResult.success(),
        }

    return consult


# ── Node 3: apply_and_validate ───────────────────────────────────────
@validated_node(ApplyAndValidateInput)
def apply_and_validate(inp: ApplyAndValidateInput, state: dict) -> dict:
    """Apply the patch, validate, save."""

    # Apply
    patch = ProjectPatch.model_validate(inp.patch)
    project = apply_patch(inp.project, patch)

    # Validate
    issues = validate_project(project)
    errors = [i.message for i in issues if i.severity == "error"]

    # Always save (drafts are fine)
    STORE.save_project(project)

    return {
        "project": project,
        "validation_errors": errors,
        "questions": [
            "Fix the following issues:",
            *[f"- {e}" for e in errors],
        ] if errors else [],
        "node_result": NodeResult.success(),
    }


# ── Routers (pure functions that inspect state) ─────────────────────
def _route_after_node(state: IntakeState) -> str:
    """Check node_result first — route to handle_error on failure."""
    result = state.get("node_result")
    if result and not result.ok:
        return "handle_error"
    return "continue"


def _route_after_control(state: IntakeState) -> str:
    """done → END, otherwise → consult."""
    return "__end__" if state["stage"] == "done" else "consult"


def _route_after_validate(state: IntakeState) -> str:
    """Errors → consult (fix them), clean → control (next stage)."""
    return "consult" if state.get("validation_errors") else "control"


# ── Build ────────────────────────────────────────────────────────────
def build_graph(
    ask_human: AskHuman = default_ask_human,
    call_ai: CallAI = default_call_ai,
):
    """Build the intake graph.

    Parameters
    ----------
    ask_human : AskHuman
        Callable that presents questions to a human and returns free text.
        Default: deterministic stub.
    call_ai : CallAI
        Callable that turns project context + human text into a ProjectPatch.
        Default: deterministic stub.

    Topology
    --------
        START → control
        control →  END | consult
        consult → apply_and_validate
        apply_and_validate → consult | control
    """
    g = StateGraph(IntakeState)

    # Nodes
    g.add_node("control", control)
    g.add_node("consult", _make_consult_node(ask_human, call_ai))
    g.add_node("apply_and_validate", apply_and_validate)
    g.add_node("handle_error", handle_error)

    # Edges — each node routes through _route_after_node first
    g.add_edge(START, "control")
    g.add_conditional_edges("control", _route_after_control, ["consult", END])
    g.add_conditional_edges("consult", _route_after_node,
                            {"continue": "apply_and_validate", "handle_error": "handle_error"})
    g.add_conditional_edges("apply_and_validate", _route_after_validate, ["consult", "control"])
    g.add_edge("handle_error", END)

    return g.compile()
