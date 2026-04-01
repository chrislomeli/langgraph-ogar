"""
ogar.hitl.gate

HumanApprovalGate interface — abstraction over human-in-the-loop pausing.

What "human in the loop" means here
─────────────────────────────────────
The supervisor agent can reach a point where it has high confidence
that something significant is happening (e.g. a real fire, not sensor
noise) but the consequences of acting are large enough that a human
should confirm before actuators fire.

At that point the agent calls gate.wait_for_approval().
Execution suspends.  The human is notified.  When the human responds
(approve or reject), execution resumes with the decision.

Why this abstraction exists
────────────────────────────
Two implementations will exist:

  ConsoleApprovalGate (stub in hitl/stub.py)
    → Prints a request to the terminal.
    → A separate coroutine calls gate.respond() to simulate the human.
    → Good for demos where you want to show the pause/resume behaviour
      without needing a web UI.

  TemporalApprovalGate (hitl/temporal.py — future)
    → The workflow calls workflow.wait_for_signal("human_approval").
    → The workflow is suspended in Temporal, survives restarts.
    → A human clicks a button in a web UI which sends an HTTP request
      that signals the workflow.
    → The Temporal UI shows the workflow sitting in WAITING state.

The supervisor agent code calls gate.wait_for_approval() in both cases.
The gate implementation handles the mechanics.

ApprovalRequest and ApprovalResult
────────────────────────────────────
ApprovalRequest carries everything a human needs to make a decision:
  - What the agent detected
  - Why it wants to act
  - What action it proposes to take

ApprovalResult carries the human's decision back to the agent:
  - approved: bool
  - reason: optional human-provided explanation
  - modifications: optional dict if the human wants to change the action
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel


# ── Data models ───────────────────────────────────────────────────────────────

class ApprovalRequest(BaseModel):
    """
    Everything the agent sends when requesting human approval.

    request_id       : Unique ID for this approval request.
                       Used to match the request to the response.
    cluster_id       : Which cluster triggered this request.
    situation_summary: Human-readable description of what was detected.
    proposed_action  : What the agent wants to do if approved.
                       e.g. "Dispatch suppression resources to grid C4"
    confidence       : Agent's confidence level 0.0–1.0.
                       Lets the human see how certain the agent is.
    context          : Any additional data the human might want.
                       e.g. sensor readings, recent anomaly history.
    """
    request_id: str
    cluster_id: str
    situation_summary: str
    proposed_action: str
    confidence: float
    context: Dict[str, Any] = {}


class ApprovalResult(BaseModel):
    """
    The human's response to an approval request.

    request_id    : Matches the ApprovalRequest.request_id this responds to.
    approved      : True if the human approves the proposed action.
    reason        : Optional explanation from the human.
    modifications : Optional dict if the human wants to change the proposed
                    action before it executes.
                    e.g. {"target_grid": "C5"} to redirect the actuator.
    """
    request_id: str
    approved: bool
    reason: Optional[str] = None
    modifications: Dict[str, Any] = {}


# ── Interface ─────────────────────────────────────────────────────────────────

class HumanApprovalGate(ABC):
    """
    Abstract interface for pausing agent execution pending human approval.

    The supervisor agent holds a reference to a HumanApprovalGate.
    It does not know whether the gate is backed by a console prompt,
    a Temporal signal, a Slack message, or a web UI.
    """

    @abstractmethod
    async def wait_for_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """
        Submit an approval request and wait for a human response.

        This coroutine suspends until the human responds via respond().
        The agent awaits this — from the agent's perspective it simply
        blocks at this line until the decision arrives.

        In the asyncio stub, the coroutine waits on an asyncio.Event.
        In Temporal, the workflow waits on a Temporal signal.
        Both resume with an ApprovalResult when the human decides.
        """
        ...

    @abstractmethod
    async def respond(self, result: ApprovalResult) -> None:
        """
        Deliver a human's decision to a waiting approval request.

        Called by:
          - A test or scenario script (in stub mode)
          - An HTTP endpoint hit by a web UI button (in production)
          - A Temporal signal handler (in Temporal mode)

        If no request with result.request_id is pending, this should
        log a warning and discard the response gracefully.
        """
        ...
