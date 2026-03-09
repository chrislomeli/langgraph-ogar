# scripts/run_intake_llm.py
"""
Run the intake graph with a REAL LLM (GPT-4o-mini) instead of stubs.

The ask_the_human stub still provides canned input (so you don't have
to type). But call_the_ai is now a real LLM call that produces
structured ProjectPatch output.

Compare the output with run_intake.py (deterministic stubs) to see
the difference.
"""
from ogar.runtime.graph.intake import build_intake_graph
from ogar.domain.consult.call_the_ai_llm import call_the_ai_llm


def main():
    # Build the intake graph with the LLM implementation swapped in.
    # ask_human stays as the default stub (canned replies).
    # call_ai is now the real LLM.
    graph = build_intake_graph(call_ai=call_the_ai_llm)

    out = graph.invoke({
        "pid": "proj_demo_llm",
        "project": None,
        "stage": "",
        "questions": [],
        "human_reply": None,
        "patch": None,
        "validation_errors": [],
        "node_result": None,
    })

    print("\n=== Done (LLM mode) ===")
    print("Final stage:", out.get("stage"))
    project = out.get("project")
    if project:
        print(f"Title: {project.title}")
        print(f"\nGoals ({len(project.goals)}):")
        for gid, g in project.goals.items():
            print(f"  [{gid}] {g.statement}")
            for m in g.success_metrics:
                print(f"    ✓ {m}")
        print(f"\nRequirements ({len(project.requirements)}):")
        for rid, r in project.requirements.items():
            print(f"  [{rid}] ({r.type}) {r.statement}")
            print(f"    Goals: {r.source_goal_ids}")
            for ac in r.acceptance_criteria:
                print(f"    ✓ {ac}")


if __name__ == "__main__":
    main()
