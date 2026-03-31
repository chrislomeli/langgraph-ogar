"""
consult — AI and human interaction layer.

Protocols
---------
AskHuman   Present questions to a human, return free-text reply.
CallAI     Given project context + human reply, return a ProjectPatch.

Implementations
---------------
ask_the_human.ask_the_human   Stub (canned replies).
call_the_ai.call_the_ai       Stub (deterministic mock patches).

Swap in any callable that matches the Protocol signature.
"""
from __future__ import annotations

from typing import List, Protocol

from starter.model.project import Project
from starter.consult.patches import ProjectPatch


class AskHuman(Protocol):
    """Interface: present questions to a human, get free-text back."""
    def __call__(self, stage: str, questions: List[str]) -> str: ...


class CallAI(Protocol):
    """Interface: turn project context + human text into a ProjectPatch."""
    def __call__(self, project: Project, stage: str, human_reply: str) -> ProjectPatch: ...
