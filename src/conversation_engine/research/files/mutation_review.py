"""
Mutation review protocol and implementations.

The MutationReviewer protocol defines the interface between the
mutate_graph node and whatever surface reviews proposed changes.

Two implementations:
  AutoApproveReviewer  : stub — approves everything, logs to stdout.
                         Use during development and testing.
  HumanReviewer        : real — surfaces the diff via LangGraph interrupt()
                         and waits for human approval. To be implemented
                         when the UI layer is ready.

Every node that mutates the graph calls reviewer.review(proposal) and
checks proposal.approved before committing. This pattern ensures the
real reviewer slots in without touching any node logic.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from conversation_engine.graph.state import MutationReview

logger = logging.getLogger(__name__)


class MutationReviewer(ABC):
    """
    Protocol for reviewing proposed graph mutations.

    Implementations decide whether to auto-approve, interrupt for human
    review, or reject. The mutate_graph node calls review() and trusts
    the result — it does not know which implementation is in use.
    """

    @abstractmethod
    def review(self, proposal: MutationReview) -> MutationReview:
        """
        Review a proposed set of mutations.

        Args:
            proposal: The proposed changes with rationale.

        Returns:
            The same proposal with approved and reviewer_note filled in.
        """
        ...


class AutoApproveReviewer(MutationReviewer):
    """
    Stub reviewer — auto-approves all proposals.

    Logs each proposal so the behavior is visible during development.
    Satisfies the MutationReviewer interface so it can be replaced
    with HumanReviewer without changing any node code.
    """

    def review(self, proposal: MutationReview) -> MutationReview:
        logger.info(
            "AutoApproveReviewer: approving %d change(s). Rationale: %s",
            len(proposal.proposed_changes),
            proposal.rationale,
        )
        for change in proposal.proposed_changes:
            logger.debug("  [%s] %s — %s", change.kind, change.node_or_edge_id, change.description)

        return MutationReview(
            proposed_changes=proposal.proposed_changes,
            rationale=proposal.rationale,
            is_reversible=proposal.is_reversible,
            approved=True,
            reviewer_note="Auto-approved (stub reviewer)",
        )


class HumanReviewer(MutationReviewer):
    """
    Real reviewer — surfaces proposed mutations to the human via interrupt().

    NOT YET IMPLEMENTED. Placeholder shows the intended interface.

    Implementation will:
      1. Write the proposal to ConversationState.pending_review
      2. Call langgraph.interrupt() to pause graph execution
      3. Resume when the human provides a decision
      4. Return the approved/rejected proposal
    """

    def review(self, proposal: MutationReview) -> MutationReview:
        raise NotImplementedError(
            "HumanReviewer is not yet implemented. "
            "Use AutoApproveReviewer during development."
        )
