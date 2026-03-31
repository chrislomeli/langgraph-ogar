"""
Prompt Templates -- M12: Structured prompts for LLM-backed planning.

KEY CONCEPT: Prompt templates define the contract between the graph and
an LLM. They produce structured messages (system + user) that an LLM
can consume to generate a PlanBundle.

For now these are just data structures -- no LLM is called. The
DeterministicStrategy ignores them entirely. But when you swap in a
real LLM, these templates define exactly what the model sees.

Templates:
  - PLAN_SYSTEM_PROMPT: instructs the LLM on how to produce a PlanBundle
  - build_plan_user_prompt: formats the user's sketch into a structured prompt
  - REFINE_SYSTEM_PROMPT: instructs the LLM on how to refine an existing plan
  - build_refine_user_prompt: formats the refinement request
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class PromptMessage:
    """A single message in a prompt (system or user role)."""
    role: str    # "system" or "user"
    content: str


@dataclass(frozen=True)
class PromptTemplate:
    """A structured prompt: system message + user message."""
    messages: list[PromptMessage] = field(default_factory=list)

    def to_dicts(self) -> list[dict[str, str]]:
        """Convert to list of dicts for LLM consumption."""
        return [{"role": m.role, "content": m.content} for m in self.messages]


# -- Plan Creation Prompts -----------------------------------------

PLAN_SYSTEM_PROMPT = """You are a music composition engine. Given a user's description of a piece of music, produce a detailed PlanBundle in JSON format.

The PlanBundle must include:
- title: a creative title for the piece
- key: the musical key (e.g., "A minor", "C major")
- tempo_bpm: tempo in BPM (integer)
- voice_plan: list of voices with name, role, and instrument
- form_plan: list of sections with name, bars, and repeats
- harmony_plan: chord progressions per section
- groove_plan: rhythmic patterns and density

Output ONLY valid JSON matching the PlanBundle schema. No explanations."""


REFINE_SYSTEM_PROMPT = """You are a music composition engine. You are refining an existing composition plan.

Given the current PlanBundle (JSON) and the user's refinement request, produce an updated PlanBundle.

Rules:
- Only change what the user asks for
- Preserve all unmentioned aspects of the plan
- If adding sections, place them logically in the form
- If changing voices, maintain musical coherence

Output ONLY the updated PlanBundle as valid JSON. No explanations."""


def build_plan_user_prompt(sketch: Any) -> PromptTemplate:
    """Build a prompt template for creating a new plan from a sketch.

    Args:
        sketch: A Sketch object with prompt and optional hints.

    Returns:
        A PromptTemplate with system and user messages.
    """
    user_content = f"Create a composition plan for: {sketch.prompt}"

    if hasattr(sketch, 'key') and sketch.key:
        user_content += f"\nKey: {sketch.key}"
    if hasattr(sketch, 'tempo') and sketch.tempo:
        user_content += f"\nTempo: {sketch.tempo} BPM"
    if hasattr(sketch, 'form_hint') and sketch.form_hint:
        user_content += f"\nForm: {sketch.form_hint}"

    return PromptTemplate(messages=[
        PromptMessage(role="system", content=PLAN_SYSTEM_PROMPT),
        PromptMessage(role="user", content=user_content),
    ])


def build_refine_user_prompt(plan: Any, prompt: str) -> PromptTemplate:
    """Build a prompt template for refining an existing plan.

    Args:
        plan: The current PlanBundle to refine.
        prompt: The user's refinement request.

    Returns:
        A PromptTemplate with system and user messages.
    """
    plan_summary = (
        f"Current plan: '{plan.title}' in {plan.key} at {plan.tempo_bpm} BPM.\n"
        f"Voices: {', '.join(v.name for v in plan.voice_plan.voices)}\n"
        f"Sections: {', '.join(s.section_id for s in plan.form_plan.sections)}\n"
        f"Total bars: {plan.form_plan.total_bars()}"
    )

    user_content = f"{plan_summary}\n\nRefinement request: {prompt}"

    return PromptTemplate(messages=[
        PromptMessage(role="system", content=REFINE_SYSTEM_PROMPT),
        PromptMessage(role="user", content=user_content),
    ])
