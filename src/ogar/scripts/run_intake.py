# scripts/run_intake.py
"""
Run the intake graph end-to-end.

Right now ask_the_human() and call_the_ai() are stubs that return
canned data.  Swap them for real I/O and an LLM when ready.
"""
from ogar.runtime.graph import build_intake_graph as build_graph


def main():
    graph = build_graph()

    # Single invoke — the graph loops internally:
    #   control → consult → apply_and_validate → control → … → END
    out = graph.invoke({
        "pid": "proj_demo",
        "project": None,
        "stage": "",
        "questions": [],
        "human_reply": None,
        "patch": None,
        "validation_errors": [],
    })

    print("\n=== Done ===")
    print("Final stage:", out.get("stage"))
    project = out.get("project")
    if project:
        print("Title:", project.title)
        print("Goals:", list(project.goals.keys()))
        print("Requirements:", list(project.requirements.keys()))


if __name__ == "__main__":
    main()