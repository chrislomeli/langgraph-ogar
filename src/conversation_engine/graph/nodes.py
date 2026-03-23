"""
Conversation graph node implementations.

Each function takes ConversationState and returns a partial state update.

Node responsibilities:
- validate  — delegate to ConversationContext.validate(), produce Findings
- reason    — (stub) read findings, decide what to ask/do next
- respond   — (stub) format agent response as a message

These nodes are **domain-agnostic**.  They work exclusively through the
ConversationContext protocol and the Finding type.  No domain-specific
imports (KnowledgeGraph, IntegrityRule, Assessment, etc.) appear here.
"""
from __future__ import annotations

from typing import Any, Dict

from langchain_core.messages import AIMessage

from conversation_engine.graph.context import ConversationContext, Finding
from conversation_engine.graph.state import ConversationState


# ── validate ─────────────────────────────────────────────────────────

def validate(state: ConversationState) -> Dict[str, Any]:
    """
    Delegate validation to the injected ConversationContext.

    The context owns all domain logic (what to validate, how to
    evaluate rules, how to map violations to findings).  This node
    simply asks it to run and stores the result.
    """
    ctx: ConversationContext = state["context"]
    prior_findings = state.get("findings", [])

    result = ctx.validate(prior_findings)

    return {
        "findings": result.findings,
        "status": "running",
    }


# ── reason (stub) ───────────────────────────────────────────────────

def reason(state: ConversationState) -> Dict[str, Any]:
    """
    Read current findings and decide what to communicate.

    Stub implementation: delegates summary formatting to the context
    so the *domain* controls the language.  A real implementation
    would call an LLM here.
    """
    ctx: ConversationContext = state["context"]
    open_findings = [f for f in state.get("findings", []) if not f.resolved]

    summary = ctx.format_finding_summary(open_findings)

    return {"messages": [AIMessage(content=summary)]}


# ── respond ──────────────────────────────────────────────────────────

def respond(state: ConversationState) -> Dict[str, Any]:
    """
    Advance the turn counter.

    In a real system this node would also handle formatting, tool output
    rendering, etc.  For now it simply bumps current_turn so the router
    can enforce a max-turns guard.
    """
    return {"current_turn": state.get("current_turn", 0) + 1}
