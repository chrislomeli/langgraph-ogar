from __future__ import annotations

from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
import operator

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, Send, interrupt
from langgraph.checkpoint.memory import InMemorySaver

# Optional but common for chat-style state:
from langchain.messages import AnyMessage, HumanMessage
from langgraph.graph.message import add_messages  # reducer for messages
# Or you can use MessagesState and subclass it (docs show both approaches). :contentReference[oaicite:0]{index=0}


# -------------------------
# 1) State schema + reducers
# -------------------------

class PlannerState(TypedDict, total=False):
    # If you want conversational context:
    messages: Annotated[list[AnyMessage], add_messages]  # merge semantics for message lists :contentReference[oaicite:1]{index=1}

    # Your "collaboration contract" fields:
    goals: list[str]
    constraints: list[str]

    # Reducers matter when you have parallel branches or multiple updates per super-step.
    assumptions: Annotated[list[str], operator.add]
    open_ambiguities: Annotated[list[str], operator.add]
    decisions: Annotated[list[dict], operator.add]

    # Planner/execution fields:
    plan: Optional[dict]
    execution_done: bool
    evaluation_done: bool

    # HITL:
    pending_hitl: bool


# -------------------------
# 2) CONTROL (the governor)
# -------------------------

def control(state: PlannerState) -> Command[
    Literal["clarify", "plan", "execute", "evaluate", END]
]:
    # Single place that decides the next phase.
    if state.get("open_ambiguities"):
        return Command(goto="clarify")

    if state.get("pending_hitl"):
        # You can also route to a dedicated "hitl" node if you prefer
        return Command(goto="clarify")

    if not state.get("plan"):
        return Command(goto="plan")

    if not state.get("execution_done", False):
        return Command(goto="execute")

    if not state.get("evaluation_done", False):
        return Command(goto="evaluate")

    return Command(goto=END)


# -------------------------
# 3) CLARIFY phase (HITL-friendly)
# -------------------------

def clarify(state: PlannerState) -> Command[Literal["control"]]:
    # Minimal example: if we have no goals, ask the human.
    if not state.get("goals"):
        user_input = interrupt({
            "message": "I need at least one goal to proceed.",
            "request": "Please provide the primary goal (1-2 sentences)."
        })
        # When resumed, interrupt() returns the resume value. :contentReference[oaicite:2]{index=2}
        return Command(
            update={"goals": [user_input["goal"]], "pending_hitl": False},
            goto="control",
        )

    # Example: detect ambiguity (placeholder logic)
    new_ambiguities = []
    if "success metric" not in " ".join(state.get("constraints", [])).lower():
        new_ambiguities.append("Define success metrics (how will we know we’re done?)")

    if new_ambiguities:
        # You might choose to interrupt here too, or just record and loop.
        return Command(update={"open_ambiguities": new_ambiguities}, goto="control")

    return Command(goto="control")


# -------------------------
# 4) PLAN phase (includes Send fan-out example)
# -------------------------

def plan(state: PlannerState) -> Command[Literal["critique_candidate", "control"]]:
    # Create N plan candidates (toy).
    candidates = [
        {"id": "A", "steps": ["Step 1", "Step 2"]},
        {"id": "B", "steps": ["Step 1", "Step 2", "Step 3"]},
    ]

    # Fan out critiques in parallel via Send (map). :contentReference[oaicite:3]{index=3}
    sends = [Send("critique_candidate", {"candidate": c}) for c in candidates]
    return Command(
        update={"decisions": [{"kind": "plan_candidates", "candidates": candidates}]},
        goto=sends,  # this is the “scatter”
    )


def critique_candidate(state: PlannerState) -> Command[Literal["reduce_critiques"]]:
    # Each Send invocation provides its own small input dict.
    # Here we pretend we've critiqued the candidate.
    candidate = state["candidate"]  # from Send payload
    critique = {"candidate_id": candidate["id"], "risk": "low"}
    return Command(update={"decisions": [{"kind": "critique", "critique": critique}]}, goto="reduce_critiques")


def reduce_critiques(state: PlannerState) -> Command[Literal["control"]]:
    # In real life you’d read all critiques and choose.
    # Here we just pick a stub plan.
    chosen = {"steps": ["Step 1", "Step 2"], "chosen_by": "reduce_critiques"}
    return Command(update={"plan": chosen}, goto="control")


# -------------------------
# 5) EXECUTE + EVALUATE phases
# -------------------------

def execute(state: PlannerState) -> Command[Literal["control"]]:
    # Tool calls would usually happen here.
    return Command(update={"execution_done": True}, goto="control")


def evaluate(state: PlannerState) -> Command[Literal["control"]]:
    # Compare outputs to success metrics, detect drift, etc.
    return Command(update={"evaluation_done": True}, goto="control")


# -------------------------
# 6) Wire it up
# -------------------------

builder = StateGraph(PlannerState)

builder.add_node("control", control)
builder.add_node("clarify", clarify)
builder.add_node("plan", plan)
builder.add_node("critique_candidate", critique_candidate)
builder.add_node("reduce_critiques", reduce_critiques)
builder.add_node("execute", execute)
builder.add_node("evaluate", evaluate)

builder.add_edge(START, "control")  # static entry
# Everything else is routed dynamically by Command(goto=...)

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)