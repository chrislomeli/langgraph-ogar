"""
call_the_ai_llm — ReAct agent implementation of the CallAI Protocol.

This replaces the deterministic stub with a real LLM (GPT-4o-mini)
that uses structured output to produce a ProjectPatch.

Architecture
------------
  1. Build a system prompt that explains the project state and what stage
     we're in (goals vs requirements).
  2. Give the LLM the human's reply as the user message.
  3. Use OpenAI's structured output (with_structured_output) to force
     the response into a ProjectPatch-compatible schema.
  4. Return the ProjectPatch.

This matches the CallAI Protocol:
    (project: Project, stage: str, human_reply: str) -> ProjectPatch

No tools needed for this first version — pure structured generation.
When you want to add tools (e.g. search, read docs), you promote this
to a full ReAct agent loop with langgraph-prebuilt's create_react_agent.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from ogar.domain.models.project import Project
from ogar.domain.consult.patches import ProjectPatch


# ── Load API key ─────────────────────────────────────────────────────

load_dotenv(os.path.expanduser("~/Source/SECRETS/.env"))


# ── Response schema (LLM-friendly mirror of ProjectPatch) ───────────
# We define a separate schema here because the LLM needs clear
# field descriptions to produce good output. This gets converted
# to a ProjectPatch after generation.

class GoalOut(BaseModel):
    """A project goal."""
    gid: str = Field(description="Unique goal ID like 'g_short_name'")
    statement: str = Field(description="Clear, measurable goal statement")
    success_metrics: List[str] = Field(description="How to know this goal is met")
    priority: int = Field(default=0, description="0 = highest priority")


class RequirementOut(BaseModel):
    """A project requirement linked to goals."""
    rid: str = Field(description="Unique requirement ID like 'r_short_name'")
    type: str = Field(description="'functional' or 'nfr'")
    statement: str = Field(description="What the system must do or satisfy")
    acceptance_criteria: List[str] = Field(description="Concrete, testable criteria")
    source_goal_ids: List[str] = Field(description="Goal IDs this requirement supports")


class PatchResponse(BaseModel):
    """Structured changes to apply to the project."""
    title: Optional[str] = Field(default=None, description="Project title (set if user provided one)")
    goals: List[GoalOut] = Field(default_factory=list, description="Goals to add or update")
    requirements: List[RequirementOut] = Field(default_factory=list, description="Requirements to add or update")
    suggested_questions: List[str] = Field(default_factory=list, description="Follow-up questions for the user")


# ── System prompts ───────────────────────────────────────────────────

GOALS_SYSTEM_PROMPT = """\
You are a senior project consultant helping define project goals.

The user will describe what they want to build. Your job is to:
1. Extract a clear project title.
2. Define 2-4 well-structured goals, each with measurable success metrics.
3. Assign priority (0 = most important).

Be concise and actionable. Do not ask questions — produce goals directly
from what the user tells you.

Current project state:
{project_json}
"""

REQUIREMENTS_SYSTEM_PROMPT = """\
You are a senior project consultant helping define requirements.

The project already has these goals:
{goals_json}

The user will describe requirements or say "draft from goals".
Your job is to:
1. Define 3-6 concrete requirements, each linked to at least one goal ID.
2. Each requirement needs testable acceptance criteria.
3. Mark type as 'functional' or 'nfr' (non-functional requirement).

If the user says "draft from goals", infer reasonable requirements from the goals.

Current project state:
{project_json}
"""


# ── Convert LLM response → ProjectPatch ─────────────────────────────

def _to_patch(resp: PatchResponse) -> ProjectPatch:
    """Convert the LLM's PatchResponse into a ProjectPatch."""
    from ogar.domain.models.project import Goal, Requirement

    goals_upsert = {}
    for g in resp.goals:
        goals_upsert[g.gid] = Goal(
            gid=g.gid,
            statement=g.statement,
            success_metrics=g.success_metrics,
            priority=g.priority,
            status="active",
        )

    reqs_upsert = {}
    for r in resp.requirements:
        reqs_upsert[r.rid] = Requirement(
            rid=r.rid,
            type=r.type,
            statement=r.statement,
            acceptance_criteria=r.acceptance_criteria,
            source_goal_ids=r.source_goal_ids,
            status="draft",
        )

    return ProjectPatch(
        title=resp.title,
        goals_upsert=goals_upsert,
        requirements_upsert=reqs_upsert,
        suggested_questions=resp.suggested_questions,
    )


# ── The CallAI implementation ────────────────────────────────────────

def call_the_ai_llm(
    project: Project,
    stage: str,
    human_reply: str,
) -> ProjectPatch:
    """
    Call an LLM (GPT-4o-mini) to produce a ProjectPatch from the
    human's reply, given the current project state and stage.

    Matches the CallAI Protocol signature.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    structured_llm = llm.with_structured_output(PatchResponse)

    # Build the project context
    project_json = project.model_dump_json(indent=2)

    if stage == "goals":
        system_msg = GOALS_SYSTEM_PROMPT.format(project_json=project_json)
    elif stage == "requirements":
        goals_json = "\n".join(
            f"  {gid}: {g.statement}" for gid, g in project.goals.items()
        )
        system_msg = REQUIREMENTS_SYSTEM_PROMPT.format(
            goals_json=goals_json,
            project_json=project_json,
        )
    else:
        system_msg = f"You are a project consultant. Current stage: {stage}\n{project_json}"

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": human_reply},
    ]

    print(f"\n  [LLM] Calling GPT-4o-mini for stage='{stage}'...")
    resp: PatchResponse = structured_llm.invoke(messages)
    print(f"  [LLM] Got response: {len(resp.goals)} goals, {len(resp.requirements)} reqs")

    return _to_patch(resp)
