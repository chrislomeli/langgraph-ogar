"""
Run the intake graph with a ReAct agent (LLM + tools).

This demonstrates:
  - The LLM can call tools (count_goals, check_coverage) during reasoning
  - Tool results flow back into the agent's reasoning loop
  - The final answer is a structured ProjectPatch, same as the stub/LLM versions

Compare with:
  - run_intake.py      — deterministic stubs (no LLM)
  - run_intake_llm.py  — LLM structured output (no tools)
  - run_intake_react.py — THIS: LLM + tools (ReAct pattern)

All three produce the same output type (ProjectPatch) because they all
implement the CallAI Protocol. The graph doesn't know or care which one
is running.
"""
from ogar.runtime.graph.intake import build_intake_graph
from ogar.domain.consult.call_the_ai_react import call_the_ai_react
from ogar.domain.consult.ask_the_human import ask_the_human


def main():
    # Build intake graph with ReAct agent for AI, stub for human
    graph = build_intake_graph(call_ai=call_the_ai_react)

    out = graph.invoke({
        "pid": "proj_react_demo",
        "project": None,
        "stage": "",
        "questions": [],
        "human_reply": None,
        "patch": None,
        "validation_errors": [],
        "node_result": None,
    })

    print("\n=== ReAct Intake Complete ===")
    print("Final stage:", out.get("stage"))
    project = out.get("project")
    if project:
        print("Title:", project.title)
        print("Goals:", list(project.goals.keys()))
        print("Requirements:", list(project.requirements.keys()))
        print(f"\nGoal details:")
        for gid, g in project.goals.items():
            print(f"  {gid}: {g.statement}")
            for m in g.success_metrics:
                print(f"    ✓ {m}")
        print(f"\nRequirement details:")
        for rid, r in project.requirements.items():
            print(f"  {rid}: {r.statement}")
            print(f"    linked to: {r.source_goal_ids}")


if __name__ == "__main__":
    main()
