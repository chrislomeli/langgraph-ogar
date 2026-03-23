"""
Conversation engine state schema and subgraph contract.

This module defines:
  - ConversationInput  : what the parent graph passes in at entry
  - ConversationOutput : what the subgraph returns at exit
  - ConversationState  : internal state carried across all nodes
  - Supporting models  : InterruptionPolicy, AnchoredExchange, BeliefChange

Design principles:
  - ConversationInput/Output define the subgraph boundary — nothing inside
    the subgraph reaches outside this contract.
  - ConversationState is never exposed to the parent graph.
  - InterruptionPolicy is injected at entry, fixed during the session,
    but designed so a future inject_policy node can swap it mid-session
    without touching any other node (reads from state, not hardcoded).
  - All fields are typed — no bare dicts, no Any.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, Field
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

from conversation_engine.models.assessment import Assessment, AssessmentType
from conversation_engine.models.rules import IntegrityRule
from conversation_engine.models.queries import GraphQueryPattern
from conversation_engine.storage.graph import KnowledgeGraph


# ── Exit reasons ─────────────────────────────────────────────────────────────

ExitReason = Literal["complete", "hand_off", "error", "max_turns"]

ConversationStatus = Literal[
    "running",       # normal operation
    "interrupted",   # waiting for human input
    "complete",      # conversation reached natural conclusion
    "hand_off",      # parent graph needs to take over
    "error",         # unrecoverable error
]


# ── Belief change tracking ────────────────────────────────────────────────────

ChangeKind = Literal[
    "node_added",
    "node_updated",
    "edge_added",
    "edge_removed",
    "assessment_resolved",
    "assessment_added",
]


class BeliefChange(BaseModel):
    """
    A single mutation to the knowledge graph or assessment list.

    Recorded inside an AnchoredExchange so every graph change is
    traceable to the conversation turn that caused it.
    """
    kind: ChangeKind = Field(..., description="Type of change")
    node_or_edge_id: str = Field(
        ..., description="ID of the affected node, edge, or assessment"
    )
    description: str = Field(
        ..., description="Human-readable summary of what changed and why"
    )


class AnchoredExchange(BaseModel):
    """
    A conversation turn that produced a meaningful change to the belief state.

    Not every turn produces an AnchoredExchange — only turns where the
    human input actually changed something in the graph or resolved an
    assessment. This keeps the anchor list signal-rich, not exhaustive.
    """
    id: str = Field(..., description="Unique identifier for this exchange")
    turn_number: int = Field(..., description="Which conversation turn this was")

    triggered_by_assessment_id: Optional[str] = Field(
        None,
        description="Assessment that prompted this exchange, if any"
    )

    human_message: str = Field(..., description="What the human said")
    agent_response: str = Field(..., description="What the agent said in reply")

    belief_changes: List[BeliefChange] = Field(
        default_factory=list,
        description="What changed in the graph as a result of this exchange"
    )

    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Interruption policy ───────────────────────────────────────────────────────

class InterruptionPolicy(BaseModel):
    """
    Compound interruption policy — three independent triggers, all evaluated.

    Injected at entry via ConversationInput. Fixed for the session lifetime,
    but designed so a future inject_policy node can replace it mid-session
    by writing a new instance to ConversationState.policy. Every node reads
    the policy from state — nothing is hardcoded.
    """
    # Trigger 1: confidence-based
    confidence_threshold: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        description=(
            "Interrupt if any active assessment has confidence below this level. "
            "Lower values = more autonomous. Higher values = more cautious."
        )
    )

    # Trigger 2: assessment-type-based (always interrupt regardless of confidence)
    always_interrupt_on: List[AssessmentType] = Field(
        default_factory=list,
        description=(
            "Assessment types that always trigger an interrupt, regardless of "
            "confidence. Use for high-stakes or irreversible finding types."
        )
    )

    # Trigger 3: explicit graph checkpoints
    explicit_checkpoints: List[str] = Field(
        default_factory=list,
        description=(
            "Node names (in the LangGraph sense) that always pause for human "
            "review before executing. Useful for milestone gates."
        )
    )

    # Autonomous run limit — forces check-in even with no assessments
    max_autonomous_turns: int = Field(
        5,
        ge=1,
        description=(
            "Force a human check-in after this many consecutive autonomous turns, "
            "even if no interruption triggers have fired."
        )
    )

    # Mutation safety
    pause_before_irreversible: bool = Field(
        True,
        description=(
            "Pause before any graph mutation that cannot be undone (e.g., "
            "node deletion). Stub-safe: the mutation reviewer enforces this."
        )
    )

    model_config = {"frozen": True}


# ── Mutation review protocol ──────────────────────────────────────────────────

class MutationReview(BaseModel):
    """
    A proposed set of belief changes awaiting review.

    This is the interface between mutate_graph and the review surface
    (human UI, auto-approver, or future interrupt). The stub implementation
    auto-approves all proposals. The real implementation will surface the
    diff to the human and wait for approval via interrupt/resume.
    """
    proposed_changes: List[BeliefChange] = Field(
        ..., description="Changes the agent wants to make to the graph"
    )
    rationale: str = Field(
        ..., description="Why the agent is proposing these changes"
    )
    is_reversible: bool = Field(
        True, description="Whether these changes can be undone"
    )

    # Filled in after review
    approved: Optional[bool] = Field(
        None, description="None = pending, True = approved, False = rejected"
    )
    reviewer_note: Optional[str] = Field(
        None, description="Human note attached to the review decision"
    )


# ── Subgraph contract ─────────────────────────────────────────────────────────

class ConversationInput(BaseModel):
    """
    What the parent graph passes into the conversation subgraph at entry.

    The parent graph owns: session identity, domain rules, query patterns,
    and the interruption policy. The subgraph owns: the conversation itself.

    Design note: passing an existing graph allows the parent to pre-populate
    the belief state (e.g., from a previous session or a bootstrapped ontology).
    Passing an empty KnowledgeGraph starts fresh.
    """
    session_id: str = Field(..., description="Parent-owned session identifier")

    initial_graph: KnowledgeGraph = Field(
        default_factory=KnowledgeGraph,
        description="Pre-populated graph or empty — subgraph mutates a copy"
    )

    rules: List[IntegrityRule] = Field(
        default_factory=list,
        description="Integrity rules the validation node will evaluate"
    )

    query_patterns: List[GraphQueryPattern] = Field(
        default_factory=list,
        description="Query patterns available to the reasoning node as tools"
    )

    policy: InterruptionPolicy = Field(
        default_factory=InterruptionPolicy,
        description=(
            "Interruption policy. Fixed at entry. Design for injection: "
            "a future inject_policy node can write a new instance to state."
        )
    )

    system_prompt: Optional[str] = Field(
        None,
        description=(
            "Optional system prompt override. If None, the subgraph uses its "
            "default prompt. Allows the parent to specialize the agent's persona."
        )
    )

    model_config = {"arbitrary_types_allowed": True}


class ConversationOutput(BaseModel):
    """
    What the conversation subgraph returns to the parent graph at exit.

    The parent graph receives the final belief state and a summary — it
    does not receive the internal conversation mechanics (messages, turn
    count, etc.). Those are internal concerns.
    """
    session_id: str

    final_graph: KnowledgeGraph = Field(
        ..., description="The mutated knowledge graph after conversation"
    )

    open_assessments: List[Assessment] = Field(
        default_factory=list,
        description="Assessments that were not resolved during this session"
    )

    resolved_assessments: List[Assessment] = Field(
        default_factory=list,
        description="Assessments that were addressed and closed"
    )

    anchored_exchanges: List[AnchoredExchange] = Field(
        default_factory=list,
        description="Exchanges that produced meaningful belief state changes"
    )

    session_summary: str = Field(
        ..., description="Human-readable summary of what happened in this session"
    )

    exit_reason: ExitReason = Field(
        ..., description="Why the conversation ended"
    )

    model_config = {"arbitrary_types_allowed": True}


# ── Internal state ────────────────────────────────────────────────────────────

class ConversationState(BaseModel):
    """
    Internal state carried across all nodes in the conversation subgraph.

    Never exposed to the parent graph. Persisted via the Postgres
    checkpointer so sessions can be resumed after failure or interruption.

    The messages field uses LangGraph's add_messages reducer — messages
    accumulate across turns, they are never replaced.

    Field ownership:
      Passed in from parent  → graph, rules, query_patterns, policy, session_id
      Built during session   → assessments, anchored_exchanges, messages, turn
      Control flow           → status, interrupt_reason, pending_review
    """

    # ── Passed in from parent ────────────────────────────────
    session_id: str
    rules: List[IntegrityRule] = Field(default_factory=list)
    query_patterns: List[GraphQueryPattern] = Field(default_factory=list)
    policy: InterruptionPolicy = Field(default_factory=InterruptionPolicy)
    system_prompt: Optional[str] = None

    # ── Belief state ─────────────────────────────────────────
    # KnowledgeGraph is not a Pydantic model — stored as-is,
    # serialized to/from JSON by custom checkpointer adapter (to be built).
    graph: Optional[KnowledgeGraph] = Field(
        default=None, description="The live knowledge graph"
    )

    # ── Assessments ──────────────────────────────────────────
    active_assessments: List[Assessment] = Field(
        default_factory=list,
        description="Current open findings from validation"
    )
    resolved_assessments: List[Assessment] = Field(
        default_factory=list,
        description="Findings that have been addressed"
    )

    # ── Exchange history ─────────────────────────────────────
    anchored_exchanges: List[AnchoredExchange] = Field(
        default_factory=list,
        description="Turns that produced meaningful belief state changes"
    )

    # ── Conversation messages ────────────────────────────────
    # Annotated with add_messages so LangGraph accumulates across turns
    messages: Annotated[List[BaseMessage], add_messages] = Field(
        default_factory=list
    )

    current_turn: int = Field(default=0)
    autonomous_turn_count: int = Field(
        default=0,
        description="Consecutive turns without a human interrupt"
    )

    # ── Control flow ─────────────────────────────────────────
    status: ConversationStatus = Field(default="running")
    interrupt_reason: Optional[str] = Field(
        default=None,
        description="Human-readable reason the last interrupt was triggered"
    )

    # ── Mutation review ──────────────────────────────────────
    pending_review: Optional[MutationReview] = Field(
        default=None,
        description=(
            "Proposed mutations awaiting review. None = no pending review. "
            "Stub auto-approves. Real implementation interrupts here."
        )
    )

    model_config = {"arbitrary_types_allowed": True}
