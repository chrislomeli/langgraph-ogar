from starter.model.project import Project, Goal, UncertaintyItem, Ref
from starter.store import JsonFileProjectStore
from starter.engine import validate_project

def main() -> None:
    store = JsonFileProjectStore("./data")

    p = Project(
        pid="proj_agentic_planner",
        title="Agentic Project Planning Tool (Demo)",
        non_goals=["Not building a sellable multi-user commercial product"],
    )

    # Goals (from our earlier tightening)
    p.goals["g_demo_tool"] = Goal(
        gid="g_demo_tool",
        statement="Build a working single-user agentic project planning tool that an LLM can use as a tool.",
        success_metrics=[
            "Create/edit/retrieve a project plan via API or CLI",
            "Pause and resume execution after hours/days",
            "Generate stale/blocker/orphan uncertainty reports",
            "End-to-end demo script runs successfully",
        ],
        priority=0,
        status="active",
    )

    p.goals["g_consistency"] = Goal(
        gid="g_consistency",
        statement="Enforce a consistent collaboration workflow via schema and deterministic gating.",
        success_metrics=[
            "Project-level uncertainty register",
            "Deterministic validators catch missing links/fields",
            "Next-runnable-step scheduling works from templates",
        ],
        priority=0,
        status="active",
    )

    # Seed an uncertainty (blocker)
    p.uncertainties["u_ui_scope"] = UncertaintyItem(
        uid="u_ui_scope",
        kind="open_question",
        text="Is v1 CLI-only, API-only, or minimal UI required for the demo?",
        impact="high",
        blocks_progress=True,
        links=[Ref(type="goal", id="g_demo_tool")],
    )

    issues = validate_project(p)
    if issues:
        print("Validation issues:")
        for i in issues:
            print("-", i)
    else:
        print("No validation issues.")

    store.save_project(p)
    print("Saved:", p.pid)

if __name__ == "__main__":
    main()