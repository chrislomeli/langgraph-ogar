# scripts/run_ogar.py
"""
Run the full OGAR graph end-to-end.

This exercises the complete pipeline:
  intake → planner → tool_select → execute → verify → decide → finalize

All phases use stubs right now. Replace them one at a time:
  1. Swap call_the_ai stub for a real LLM in intake
  2. Wire PlanOrchestrator into the planner subgraph
  3. Wire ToolClient into the execute subgraph
"""
from ogar.runtime.graph import build_ogar_graph

def main():
    graph = build_ogar_graph()

    out = graph.invoke({
        "pid": "proj_demo",
        "project": None,
        "stage": "",
        "questions": [],
        "human_reply": None,
        "patch": None,
        "validation_errors": [],
        "plan_steps": [],
        "current_step_index": 0,
        "tool_request": None,
        "tool_response": None,
        "tool_error": None,
        "retry_count": 0,
        "run_status": "running",
        "audit_log": [],
        "decision": "",
        "node_result": None,
    })

    print("\n=== OGAR Run Complete ===")
    print(f"Status: {out.get('run_status')}")

    project = out.get("project")
    if project:
        print(f"Title:  {project.title}")
        print(f"Goals:  {list(project.goals.keys())}")
        print(f"Reqs:   {list(project.requirements.keys())}")

    steps = out.get("plan_steps", [])
    if steps:
        print(f"\nPlan ({len(steps)} steps):")
        for s in steps:
            print(f"  [{s['status']}] {s['title']}")

    audit = out.get("audit_log", [])
    if audit:
        print(f"\nAudit log ({len(audit)} events):")
        for e in audit:
            print(f"  {e}")


if __name__ == "__main__":
    main()
