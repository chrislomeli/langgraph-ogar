"""
Use Case 2: Planning a novel with 25 chapters.

Proves the project engine is domain-generic — same graph model,
different system prompt. The agent:
  1. Explores the book concept
  2. Proposes a chapter plan with dependencies
  3. Approves and shows writing order

Prerequisites:
  1. Memgraph running on localhost:7687
  2. OPENAI_API_KEY set (or in ~/Source/SECRETS/.env)

Usage:
  python examples/demo_uc2_book.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

env_path = Path.home() / "Source" / "SECRETS" / ".env"
if env_path.exists():
    load_dotenv(env_path)

from langchain_core.messages import HumanMessage

from project_planner.persistence.connection import get_memgraph, ensure_schema
from project_planner.persistence.commands import (
    create_actor, create_project, create_work_item,
    create_outcome, set_project_root,
)
from project_planner.graph.agent import build_agent


DOMAIN_HINT = """\
Domain: Novel Writing.
You are helping an author plan and organize a novel. In this domain:
- A "milestone" represents a major story arc or act (e.g., Act I, Act II, Act III)
- A "task" represents a chapter to write
- A "research" item represents worldbuilding or character development work
- A "note" records character motivations, plot points, or thematic ideas
- An "outcome" represents a narrative goal (e.g., "Reader understands the protagonist's flaw")
- Dependencies mean "this chapter should be written after that one" (narrative order or setup)
- Priority indicates writing order preference (higher = write sooner)

Think like a developmental editor helping structure a compelling narrative."""


def seed():
    db = get_memgraph()
    db.execute("MATCH (n) DETACH DELETE n")
    ensure_schema(db)

    actor_id = create_actor(db, id="author", kind="human", name="Author")
    project_id = create_project(
        db, id="novel_echoes", name="Echoes of the Forgotten",
        actor_id=actor_id,
    )

    # Three-act structure as milestones
    act1 = create_work_item(
        db, id="act1", project_id=project_id,
        title="Act I: The Ordinary World",
        kind="milestone", actor_id=actor_id, state="active", priority=100,
    )
    act2 = create_work_item(
        db, id="act2", project_id=project_id,
        title="Act II: The Descent",
        kind="milestone", actor_id=actor_id, state="active", priority=90,
    )
    act3 = create_work_item(
        db, id="act3", project_id=project_id,
        title="Act III: The Return",
        kind="milestone", actor_id=actor_id, state="active", priority=80,
    )
    set_project_root(db, project_id=project_id, work_item_id=act1, actor_id=actor_id)

    # Narrative outcomes
    create_outcome(
        db, id="out_flaw", project_id=project_id,
        title="Reader understands protagonist's fatal flaw",
        criteria="Flaw is demonstrated in at least 3 chapters across Acts I and II",
        actor_id=actor_id,
    )
    create_outcome(
        db, id="out_twist", project_id=project_id,
        title="Mid-point twist lands with impact",
        criteria="Setup clues planted in Act I pay off in Ch 12-13",
        actor_id=actor_id,
    )
    create_outcome(
        db, id="out_resolution", project_id=project_id,
        title="Satisfying resolution of all character arcs",
        criteria="Every named character's arc resolves by Ch 25",
        actor_id=actor_id,
    )

    print(f"  Project: {project_id}")
    print(f"  Acts: {act1}, {act2}, {act3}")
    print(f"  Outcomes: out_flaw, out_twist, out_resolution")
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
            continue
        else:
            print(f"  [AI] {msg.content}")
    print()


def run(app, messages, user_msg):
    """Append user message, invoke, print new messages, return updated list."""
    print(f"{'─'*60}")
    print(f"AUTHOR: {user_msg}")
    print(f"{'─'*60}")
    messages.append(HumanMessage(content=user_msg))
    prev_count = len(messages)
    result = app.invoke({"messages": messages})
    messages = result["messages"]
    print_new_messages(messages, prev_count)
    return messages


def main():
    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║  Use Case 2: Novel Planning (25 Chapters, 3 Acts)      ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    print("1. Seeding project with 3-act structure and outcomes...")
    db, project_id, actor_id = seed()

    app = build_agent(
        db, project_id, actor_id,
        domain_hint=DOMAIN_HINT,
    )
    messages = []  # accumulate across turns

    # Phase 1: EXPLORING — describe the book concept
    print("\n═══ PHASE 1: EXPLORING ═══\n")
    messages = run(app, messages, (
        "I'm writing a literary thriller called 'Echoes of the Forgotten'. "
        "The protagonist, Elena, is a war correspondent who returns to her "
        "hometown and discovers that a series of disappearances are connected "
        "to a secret her family has kept for decades. Her fatal flaw is that "
        "she can't stop chasing the truth even when it destroys her relationships. "
        "The story has 25 chapters across three acts. "
        "Key characters: Elena (protagonist), Marcus (her estranged brother), "
        "Detective Okafor (ally who becomes antagonist), and Grandmother Iris "
        "(keeper of the family secret, dies in Act II). "
        "The mid-point twist is that Marcus has been protecting Elena by hiding "
        "evidence, not obstructing justice as she believed."
    ))

    # Phase 2: PLANNING — propose chapter plan
    print("\n═══ PHASE 2: PLANNING ═══\n")
    messages = run(app, messages, (
        "Great exploration. Now move to planning and propose all 25 chapters. "
        "Distribute them across the three acts: "
        "Act I (chapters 1-8), Act II (chapters 9-17), Act III (chapters 18-25). "
        "Link each chapter to its act milestone. "
        "Add dependencies where narrative order matters — especially for the "
        "mid-point twist setup. Use priorities to indicate writing order."
    ))

    # Phase 3: APPROVE & EXECUTE
    print("\n═══ PHASE 3: APPROVE & EXECUTE ═══\n")
    messages = run(app, messages, (
        "The chapter plan looks good. Approve everything and move to execution. "
        "What chapters should I write first?"
    ))

    # Phase 4: REVIEWING
    print("\n═══ PHASE 4: REVIEWING ═══\n")
    messages = run(app, messages, (
        "Move to review and give me a summary of the novel project — "
        "how many chapters are planned, what outcomes are we tracking, "
        "and what's the overall structure?"
    ))


if __name__ == "__main__":
    main()
