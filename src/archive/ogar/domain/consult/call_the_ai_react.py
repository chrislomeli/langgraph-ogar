"""
call_the_ai_react — ReAct agent implementation of the CallAI Protocol.

This extends call_the_ai_llm by giving the LLM tools it can call
during the reasoning loop. The agent follows the ReAct pattern:

    Think → Act (call tool) → Observe (tool result) → Think → … → Final Answer

Architecture
------------
  1. Define stub tools as @tool-decorated functions.
  2. Build a ReAct agent via langgraph-prebuilt's create_react_agent.
  3. The agent reasons about the project, optionally calls tools to
     gather info, then produces a structured PatchResponse.
  4. We extract the final message content and parse it into a ProjectPatch.

This matches the CallAI Protocol:
    (project: Project, stage: str, human_reply: str) -> ProjectPatch

What you learn from this
------------------------
  - How create_react_agent works (it builds a full LangGraph subgraph)
  - How to give tools to an LLM and let it decide when to use them
  - How tool results flow back into the reasoning loop
  - The bridge from your ToolSpec to LangChain's @tool decorator

To add real tools later: register them as ToolSpecs in a ToolRegistry,
wrap each in _toolspec_to_langgchain(), and pass them to the agent.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from ogar.domain.models.project import Project, Goal, Requirement
from ogar.domain.consult.patches import ProjectPatch


# ── Load API key ─────────────────────────────────────────────────────

load_dotenv(os.path.expanduser("~/Source/SECRETS/.env"))


# ── Stub tools ───────────────────────────────────────────────────────
# These are simple examples. The pattern is:
#   1. Define input/output as plain args + return type
#   2. Decorate with @tool
#   3. The LLM sees the docstring as the tool description
#
# Your ToolSpec registry is the canonical place for production tools.
# To bridge: wrap ToolSpec.handler in a @tool decorator (see below).

@tool
def count_goals(project_json: str) -> str:
    """Count the number of goals currently defined in the project.
    Input: project_json — the full project as a JSON string.
    Returns a summary of goal count and their IDs."""
    try:
        data = json.loads(project_json)
        goals = data.get("goals", {})
        if not goals:
            return "The project has 0 goals defined. You need to create some."
        ids = list(goals.keys())
        return f"The project has {len(ids)} goal(s): {', '.join(ids)}"
    except Exception as e:
        return f"Error reading project: {e}"


@tool
def check_goal_requirements_coverage(project_json: str) -> str:
    """Check which goals have requirements linked to them and which don't.
    Input: project_json — the full project as a JSON string.
    Returns a coverage report showing linked vs unlinked goals."""
    try:
        data = json.loads(project_json)
        goals = set(data.get("goals", {}).keys())
        reqs = data.get("requirements", {})

        covered = set()
        for r in reqs.values():
            for gid in r.get("source_goal_ids", []):
                covered.add(gid)

        uncovered = goals - covered
        if not uncovered:
            return f"All {len(goals)} goals have at least one requirement linked."
        return (
            f"{len(covered)}/{len(goals)} goals are covered by requirements. "
            f"Uncovered: {', '.join(sorted(uncovered))}"
        )
    except Exception as e:
        return f"Error reading project: {e}"


# ── All tools available to the agent ─────────────────────────────────

REACT_TOOLS = [count_goals, check_goal_requirements_coverage]


# ── System prompts ───────────────────────────────────────────────────

REACT_SYSTEM_PROMPT = """\
You are a senior project consultant helping define a software project.

You have tools available to inspect the current project state. USE THEM
before making decisions — don't guess about what's already defined.

Your workflow:
1. Use your tools to understand the current project state.
2. Based on the user's input and the tool results, produce your answer.

Current stage: {stage}

IMPORTANT: Your final answer MUST be valid JSON matching this schema:
{{
  "title": "string or null",
  "goals": [
    {{"gid": "g_short_name", "statement": "...", "success_metrics": ["..."], "priority": 0}}
  ],
  "requirements": [
    {{"rid": "r_short_name", "type": "functional|nfr", "statement": "...",
      "acceptance_criteria": ["..."], "source_goal_ids": ["g_..."]}}
  ],
  "suggested_questions": ["..."]
}}

If the stage is "goals", focus on producing goals (requirements can be empty).
If the stage is "requirements", focus on producing requirements (goals can be empty).

Current project state:
{project_json}
"""


# ── Response parsing ─────────────────────────────────────────────────
# Reuse the same PatchResponse model from call_the_ai_llm

class PatchResponse(BaseModel):
    """Structured changes to apply to the project."""
    title: Optional[str] = Field(default=None)
    goals: List[Dict] = Field(default_factory=list)
    requirements: List[Dict] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)


def _to_patch(resp: PatchResponse, project: Project) -> ProjectPatch:
    """Convert the agent's PatchResponse into a ProjectPatch."""
    goals_upsert = {}
    for g in resp.goals:
        gid = g.get("gid", "g_unknown")
        goals_upsert[gid] = Goal(
            gid=gid,
            statement=g.get("statement", ""),
            success_metrics=g.get("success_metrics", []),
            priority=g.get("priority", 0),
            status="active",
        )

    # Collect all known goal IDs for fallback linking
    # Include goals from this patch AND existing project goals
    all_goal_ids = list(goals_upsert.keys()) + list(project.goals.keys())
    all_goal_ids = list(dict.fromkeys(all_goal_ids))  # dedupe, preserve order

    reqs_upsert = {}
    for r in resp.requirements:
        rid = r.get("rid", "r_unknown")
        source_goal_ids = r.get("source_goal_ids", [])
        # LLMs sometimes forget to link — fallback to all goals
        if not source_goal_ids and all_goal_ids:
            source_goal_ids = all_goal_ids
        elif not source_goal_ids:
            source_goal_ids = ["g_unlinked"]
        reqs_upsert[rid] = Requirement(
            rid=rid,
            type=r.get("type", "functional"),
            statement=r.get("statement", ""),
            acceptance_criteria=r.get("acceptance_criteria", []),
            source_goal_ids=source_goal_ids,
            status="draft",
        )

    return ProjectPatch(
        title=resp.title,
        goals_upsert=goals_upsert,
        requirements_upsert=reqs_upsert,
        suggested_questions=resp.suggested_questions,
    )


def _parse_final_answer(text: str) -> PatchResponse:
    """Extract JSON from the agent's final text response."""
    # Try to find JSON block in the response
    # The agent might wrap it in ```json ... ``` or just produce raw JSON
    import re
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    else:
        # Try to find raw JSON object
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            text = json_match.group(1)

    try:
        data = json.loads(text)
        return PatchResponse(**data)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [ReAct] Warning: Could not parse JSON from agent response: {e}")
        print(f"  [ReAct] Raw text: {text[:200]}...")
        return PatchResponse()


# ── The CallAI implementation ────────────────────────────────────────

def call_the_ai_react(
    project: Project,
    stage: str,
    human_reply: str,
) -> ProjectPatch:
    """
    Call a ReAct agent (GPT-4o-mini + tools) to produce a ProjectPatch.

    The agent can use tools to inspect the project before generating
    its structured response. This is the key difference from
    call_the_ai_llm: the LLM DECIDES whether to call tools.

    Matches the CallAI Protocol signature.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)

    # Build the ReAct agent — this creates a full LangGraph subgraph internally
    agent = create_react_agent(llm, REACT_TOOLS)

    project_json = project.model_dump_json(indent=2)
    system_msg = REACT_SYSTEM_PROMPT.format(
        stage=stage,
        project_json=project_json,
    )

    print(f"\n  [ReAct] Calling agent for stage='{stage}' with {len(REACT_TOOLS)} tools...")

    result = agent.invoke({
        "messages": [
            SystemMessage(content=system_msg),
            HumanMessage(content=human_reply),
        ]
    })

    # Extract the final message from the agent
    messages = result.get("messages", [])
    if not messages:
        print("  [ReAct] Warning: No messages returned from agent")
        return ProjectPatch()

    final_msg = messages[-1]
    final_text = final_msg.content if hasattr(final_msg, "content") else str(final_msg)

    # Count tool calls for observability
    tool_call_count = sum(1 for m in messages if hasattr(m, "tool_calls") and m.tool_calls)
    print(f"  [ReAct] Agent made {tool_call_count} tool call(s), "
          f"{len(messages)} total messages in reasoning chain")

    # Parse the final answer into a PatchResponse
    resp = _parse_final_answer(final_text)
    print(f"  [ReAct] Parsed: {len(resp.goals)} goals, {len(resp.requirements)} reqs")

    return _to_patch(resp, project)
