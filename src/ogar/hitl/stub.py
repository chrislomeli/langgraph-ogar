"""
ogar.hitl.stub

ConsoleApprovalGate — asyncio stub implementation of HumanApprovalGate.

How it works
────────────
  1. Supervisor agent calls gate.wait_for_approval(request).
  2. The gate prints the request to the console (or logs it).
  3. The gate creates an asyncio.Event and waits for it to be set.
  4. A scenario script (or a test, or a CLI command) calls gate.respond().
  5. respond() stores the ApprovalResult and sets the Event.
  6. wait_for_approval() unblocks and returns the result.

This is enough to demonstrate the pause/resume pattern clearly.
The agent visibly stops, you can see it waiting, then you trigger
the approval and it continues.

Compared to Temporal
─────────────────────
With Temporal, step 3 above becomes the workflow sleeping in Temporal's
durable storage — it would survive a process restart.  Steps 1–6 work
the same from the agent's perspective.

When Temporal is added, replace ConsoleApprovalGate with
TemporalApprovalGate.  The supervisor agent code does not change.

Multiple concurrent requests
─────────────────────────────
The gate supports multiple pending approval requests simultaneously.
Each has its own asyncio.Event keyed by request_id.  This handles
the (unlikely but valid) case where two cluster agents both escalate
at the same time.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from ogar.hitl.gate import ApprovalRequest, ApprovalResult, HumanApprovalGate

logger = logging.getLogger(__name__)


class ConsoleApprovalGate(HumanApprovalGate):
    """
    Human approval gate backed by asyncio Events.

    The "console" in the name refers to how the request is surfaced —
    it's logged/printed rather than sent to a real UI.  In demo mode
    this is fine: the demo operator calls respond() directly.
    """

    def __init__(self) -> None:
        # Maps request_id → asyncio.Event.
        # The Event is set when respond() is called with that request_id.
        self._pending_events: Dict[str, asyncio.Event] = {}

        # Maps request_id → ApprovalResult.
        # Stored by respond(), retrieved by wait_for_approval().
        self._results: Dict[str, ApprovalResult] = {}

    async def wait_for_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """
        Print the approval request and block until a human responds.

        The agent awaits this coroutine — it pauses here until
        respond() is called with a matching request_id.
        """
        # ── Create the event for this request ─────────────────────────
        event = asyncio.Event()
        self._pending_events[request.request_id] = event

        # ── Surface the request to the "human" ────────────────────────
        # In demo mode this goes to the console / log.
        # In production this would send a Slack message, email, etc.
        self._print_request(request)

        # ── Suspend until respond() sets the event ────────────────────
        # This is the key moment — the agent is paused right here.
        # Nothing proceeds until respond() is called.
        logger.info(
            "HITL: waiting for approval — request_id=%s, cluster=%s",
            request.request_id,
            request.cluster_id,
        )
        await event.wait()

        # ── Retrieve and return the result ────────────────────────────
        result = self._results.pop(request.request_id)
        del self._pending_events[request.request_id]

        logger.info(
            "HITL: approval received — request_id=%s, approved=%s, reason=%r",
            request.request_id,
            result.approved,
            result.reason,
        )
        return result

    async def respond(self, result: ApprovalResult) -> None:
        """
        Deliver a human decision to a waiting approval request.

        Called by:
          - Tests: directly with an ApprovalResult
          - Scenario scripts: to simulate human approval at a specific time
          - Future: an HTTP handler when a human clicks a button in a UI

        If result.request_id doesn't match any pending request,
        the response is logged as a warning and discarded.
        """
        event = self._pending_events.get(result.request_id)
        if event is None:
            logger.warning(
                "HITL respond() called for unknown or already-resolved request_id=%s — discarding",
                result.request_id,
            )
            return

        # Store the result BEFORE setting the event, so wait_for_approval()
        # can immediately retrieve it when it unblocks.
        self._results[result.request_id] = result
        event.set()

    def pending_request_ids(self) -> list[str]:
        """
        Return a list of request IDs currently waiting for approval.

        Useful for tests and scenario scripts to know which approvals
        are outstanding.
        """
        return list(self._pending_events.keys())

    @staticmethod
    def _print_request(request: ApprovalRequest) -> None:
        """Format and print an approval request to the console."""
        print("\n" + "=" * 60)
        print("  HUMAN APPROVAL REQUIRED")
        print("=" * 60)
        print(f"  Request ID : {request.request_id}")
        print(f"  Cluster    : {request.cluster_id}")
        print(f"  Confidence : {request.confidence:.0%}")
        print(f"  Situation  : {request.situation_summary}")
        print(f"  Action     : {request.proposed_action}")
        if request.context:
            print(f"  Context    : {request.context}")
        print("=" * 60)
        print("  Call gate.respond(ApprovalResult(...)) to continue.")
        print("=" * 60 + "\n")
