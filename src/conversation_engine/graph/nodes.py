"""
Conversation graph node implementations.

Each function takes ConversationState and returns a partial state update.

Node responsibilities:
- preflight — run pre-flight LLM validation (once, on first turn)
- validate  — delegate to ConversationContext.validate(), produce Findings
- reason    — read findings, call LLM (or stub) to decide what to communicate
- respond   — advance the turn counter

These nodes are **domain-agnostic**.  They work exclusively through the
ConversationContext protocol and the Finding type.  No domain-specific
imports (KnowledgeGraph, IntegrityRule, Assessment, etc.) appear here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from langchain_core.messages import AIMessage

from conversation_engine.graph.context import ConversationContext, Finding
from conversation_engine.graph.state import ConversationState
from conversation_engine.infrastructure.llm import (
    CallLLM,
    LLMRequest,
    LLMResponse,
    LLMValidator,
    LLMValidatorReport,
    quiz_report_summary,
)

logger = logging.getLogger(__name__)


# ── preflight ────────────────────────────────────────────────────────

def preflight(state: ConversationState) -> Dict[str, Any]:
    """
    Run pre-flight LLM validation on the first turn only.

    Pulls the quiz and system prompt from the ConversationContext.
    If no LLM or no quiz is configured, passes through immediately.
    On failure, sets status='error' so the router exits the graph.
    On success (or skip), sets preflight_passed=True so subsequent
    turns bypass this node.
    """
    # Skip if already passed (subsequent turns in the loop)
    if state.get("preflight_passed", False):
        return {}

    ctx: ConversationContext = state["context"]
    llm: Optional[CallLLM] = state.get("llm")
    quiz = ctx.preflight_quiz

    # Skip if no LLM or no quiz configured
    if not llm or not quiz:
        return {"preflight_passed": True}

    # Run the validator
    validator = LLMValidator(
        llm=llm,
        system_prompt=ctx.system_prompt,
        quiz=quiz,
        pass_threshold=0.7,
    )
    report = validator.run()

    if not report.passed:
        logger.error(
            "LLM pre-flight validation failed:\n%s",
            quiz_report_summary(report),
        )
        return {
            "status": "error",
            "preflight_passed": False,
            "messages": [AIMessage(content=f"LLM failed pre-flight validation (score={report.weighted_score:.0%})")],
        }

    logger.info(
        "LLM pre-flight validation passed (score=%.0f%%)",
        report.weighted_score * 100,
    )
    return {"preflight_passed": True}


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

    If an LLM is available in state, call it with the findings and context.
    Otherwise, fall back to the context's summary formatting.
    """
    ctx: ConversationContext = state["context"]
    open_findings = [f for f in state.get("findings", []) if not f.resolved]
    llm: Optional[CallLLM] = state.get("llm")

    if llm:
        # Build the LLM request with context and findings
        findings_text = "\n".join(f"- {f.finding_type}: {f.message}" for f in open_findings)
        user_message = f"""
Current findings ({len(open_findings)}):
{findings_text}

Please analyze these findings and provide a recommendation or summary.
"""
        
        request = LLMRequest(
            system_prompt=ctx.system_prompt,
            user_message=user_message,
            context={
                "session_id": state.get("session_id"),
                "current_turn": state.get("current_turn", 0),
                "prior_messages": state.get("messages", []),
            },
        )
        
        try:
            response = llm(request)
            summary = response.content
        except Exception as e:
            # Fallback to context if LLM fails
            summary = f"LLM error: {e}. {ctx.format_finding_summary(open_findings)}"
    else:
        # No LLM available - use context summary
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
