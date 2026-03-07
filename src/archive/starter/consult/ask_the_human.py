"""
ask_the_human — stub for the human interaction layer.

In production this would be a CLI prompt, web form, Slack bot, etc.
For now it returns canned responses so the graph can run end-to-end.
"""
from __future__ import annotations

from typing import List


def ask_the_human(stage: str, questions: List[str]) -> str:
    """
    Present *questions* to the human and return their free-text reply.

    Parameters
    ----------
    stage : str
        Current project stage (e.g. "goals", "requirements").
    questions : list[str]
        Questions the system wants answered.

    Returns
    -------
    str
        The human's reply (free text).  The AI will parse this later.
    """
    # ---- STUB: replace with real I/O later ----
    if stage == "goals":
        return (
            "Title: Agentic Project Planner Demo\n"
            "Goal 1: Build a working single-user planning tool. "
            "Metrics: CLI create/edit/retrieve, pause-resume, stale report.\n"
            "Goal 2: Enforce consistent workflow via schema gating. "
            "Metrics: uncertainty register, deterministic validators."
        )

    if stage == "requirements":
        return (
            "Req 1 (functional): Interactive planning — user outlines goals, "
            "system drafts plan.  AC: drafts work items, asks clarifications.\n"
            "Req 2 (functional): Persistence — project stored and retrievable. "
            "AC: round-trip create-store-retrieve.\n"
            "Req 3 (functional): Validation — deterministic consistency checks. "
            "AC: flags missing links, flags orphans."
        )

    return "No additional input."
