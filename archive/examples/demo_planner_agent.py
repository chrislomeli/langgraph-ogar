"""
Hello World: LangGraph agent using the project engine as a todo list.

Prerequisites:
  1. Memgraph running on localhost:7687
  2. OPENAI_API_KEY set (or in ~/Source/SECRETS/.env)

Usage:
  python examples/demo_planner_agent.py
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load API keys
env_path = Path.home() / "Source" / "SECRETS" / ".env"
if env_path.exists():
    load_dotenv(env_path)

from langchain_core.messages import HumanMessage

from project_planner.persistence.connection import get_memgraph, ensure_schema
from project_planner.persistence.commands import create_actor, create_project, create_work_item, set_project_root
from project_planner.graph.agent import build_agent


def seed_demo_data():
    """Create a minimal project with one milestone for the agent to work with."""
    db = get_memgraph()
    db.execute("MATCH (n) DETACH DELETE n")
    ensure_schema(db)

    actor_id = create_actor(db, id="actor_chris", kind="human", name="Chris")
    project_id = create_project(db, id="proj_demo", name="REST API Backend", actor_id=actor_id)
    root_id = create_work_item(
        db, id="m_root", project_id=project_id,
        title="MVP: REST API with auth and CRUD",
        kind="milestone", actor_id=actor_id, state="active", priority=90,
    )
    set_project_root(db, project_id=project_id, work_item_id=root_id, actor_id=actor_id)

    print(f"  Project: {project_id}")
    print(f"  Actor:   {actor_id}")
    print(f"  Root:    {root_id}")
    return db, project_id, actor_id


def run_agent(db, project_id, actor_id, user_message: str):
    """Run the agent with a single user message and print the conversation."""
    app = build_agent(db, project_id, actor_id)

    print(f"\n{'='*60}")
    print(f"USER: {user_message}")
    print(f"{'='*60}\n")

    result = app.invoke({"messages": [HumanMessage(content=user_message)]})

    for msg in result["messages"]:
        role = msg.__class__.__name__.replace("Message", "").upper()
        if role == "AI" and hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"[AI → tool calls]")
            for tc in msg.tool_calls:
                print(f"  → {tc['name']}({tc['args']})")
        elif role == "TOOL":
            content = msg.content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"[TOOL: {msg.name}] {content}")
        elif role == "SYSTEM":
            continue
        else:
            print(f"[{role}] {msg.content}")

    print(f"\n{'='*60}\n")


def main():
    print("\n🚀 Project Planner Agent Demo\n")

    print("1. Seeding demo data...")
    db, project_id, actor_id = seed_demo_data()

    print("\n2. Running agent — asking it to plan some tasks...\n")
    run_agent(
        db, project_id, actor_id,
        "Check the current project status, then create 3 tasks for building "
        "a REST API: one for setting up the FastAPI skeleton, one for adding "
        "auth middleware, and one for writing CRUD endpoints. Link them all to "
        "milestone m_root. The auth task should depend on the skeleton task."
    )

    print("3. Running agent — asking what to work on next...\n")
    run_agent(
        db, project_id, actor_id,
        "What should I work on next? Show me my actionable tasks."
    )


if __name__ == "__main__":
    main()
