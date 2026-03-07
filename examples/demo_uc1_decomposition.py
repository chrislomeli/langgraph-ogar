"""
Use Case 1: Software task decomposition with explore → plan → execute phases.

Demonstrates the phase-aware workflow:
  1. EXPLORING — agent asks questions, records findings
  2. PLANNING  — agent proposes a plan, user reviews
  3. EXECUTING — agent works through tasks
  4. REVIEWING — agent summarizes

Prerequisites:
  1. Memgraph running on localhost:7687
  2. OPENAI_API_KEY set (or in ~/Source/SECRETS/.env)

Usage:
  python examples/demo_uc1_decomposition.py
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path.home() / "Source" / "SECRETS" / ".env"
if env_path.exists():
    load_dotenv(env_path)

from langchain_core.messages import HumanMessage

from project_planner.persistence.connection import get_memgraph, ensure_schema
from project_planner.persistence.commands import (
    create_actor, create_project, create_work_item, set_project_root,
)
from project_planner.graph.agent import build_agent


DOMAIN_HINT = """\
Domain: Software Engineering.
You are helping decompose a complex software feature request into \
well-structured tasks with dependencies. Think like a senior engineer \
doing sprint planning."""


def seed():
    db = get_memgraph()
    db.execute("MATCH (n) DETACH DELETE n")
    ensure_schema(db)

    actor_id = create_actor(db, id="chris", kind="human", name="Chris")
    project_id = create_project(db, id="proj_auth", name="User Auth System", actor_id=actor_id)
    root_id = create_work_item(
        db, id="m_auth", project_id=project_id,
        title="Ship user authentication with OAuth + email/password",
        kind="milestone", actor_id=actor_id, state="active", priority=95,
    )
    set_project_root(db, project_id=project_id, work_item_id=root_id, actor_id=actor_id)

    print(f"  Project: {project_id} — {root_id}")
    return db, project_id, actor_id


def print_new_messages(all_messages, prev_count):
    """Print only messages added since prev_count."""
    for msg in all_messages[prev_count:]:
        role = msg.__class__.__name__.replace("Message", "").upper()
        if role == "AI" and hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"  [AI → tools]")
            for tc in msg.tool_calls:
                args_short = str(tc["args"])
                if len(args_short) > 120:
                    args_short = args_short[:120] + "..."
                print(f"    → {tc['name']}({args_short})")
        elif role == "TOOL":
            content = msg.content
            if len(content) > 150:
                content = content[:150] + "..."
            print(f"  [TOOL: {msg.name}] {content}")
        elif role == "SYSTEM":
            continue
        elif role == "HUMAN":
            continue  # we already printed this
        else:
            print(f"  [AI] {msg.content}")
    print()


def run(app, messages, user_msg):
    """Append user message, invoke, print new messages, return updated list."""
    print(f"{'─'*60}")
    print(f"USER: {user_msg}")
    print(f"{'─'*60}")
    messages.append(HumanMessage(content=user_msg))
    prev_count = len(messages)
    result = app.invoke({"messages": messages})
    messages = result["messages"]
    print_new_messages(messages, prev_count)
    return messages


def main():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Use Case 1: Software Decomposition (Phase Workflow)   ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    print("1. Seeding project...")
    db, project_id, actor_id = seed()

    app = build_agent(db, project_id, actor_id, domain_hint=DOMAIN_HINT)
    messages = []  # accumulate across turns

    # Phase 1: EXPLORING — vague request, agent should ask questions / record findings
    print("\n═══ PHASE 1: EXPLORING ═══\n")
    messages = run(app, messages, (
        "I need to add user authentication to our FastAPI app. "
        "We need OAuth (Google, GitHub) and email/password. "
        "There's an existing user table in Postgres but no auth yet."
    ))

    # Phase 2: PLANNING — tell the agent to propose a plan
    print("\n═══ PHASE 2: PLANNING ═══\n")
    messages = run(app, messages, (
        "Good analysis. I'm satisfied with your understanding. "
        "Please move to the planning phase and propose a detailed task breakdown."
    ))

    # Phase 3: APPROVE + EXECUTE — approve the plan
    print("\n═══ PHASE 3: APPROVE & EXECUTE ═══\n")
    messages = run(app, messages, (
        "The plan looks good. Approve all proposed items and move to execution. "
        "Then show me what I should work on first."
    ))

    # Phase 4: REVIEWING — wrap up
    print("\n═══ PHASE 4: REVIEWING ═══\n")
    messages = run(app, messages, (
        "Let's move to the review phase and summarize the project status."
    ))


if __name__ == "__main__":
    main()
