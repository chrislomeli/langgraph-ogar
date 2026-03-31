from starter.model.project import Requirement, UncertaintyItem, Ref
from starter.store import JsonFileProjectStore
from starter.engine import validate_project, report_blocking_uncertainties

PID = "proj_agentic_planner"

def main() -> None:
    store = JsonFileProjectStore("./data")
    p = store.load_project(PID)

    print("Loaded project:", p.title)
    print("Goals:")
    for g in p.goals.values():
        print(f"- ({g.priority}) {g.gid}: {g.statement}")

    # --- Draft requirements (your client-style list, normalized) ---
    # In the LLM version, this list would be generated/refined interactively.
    p.requirements["r_interactive_planning"] = Requirement(
        rid="r_interactive_planning",
        type="functional",
        statement="User can outline project goals and interactively collaborate with the system to produce a project plan.",
        acceptance_criteria=[
            "Given a project with goals, system drafts a plan (work items + dependencies)",
            "System can ask clarification questions when blockers are detected",
        ],
        source_goal_ids=["g_demo_tool", "g_consistency"],
        status="draft",
    )

    p.requirements["r_persistence"] = Requirement(
        rid="r_persistence",
        type="functional",
        statement="Project plan is persisted in a database and can be retrieved and modified.",
        acceptance_criteria=[
            "Create project → store → retrieve yields equivalent object",
            "Modify requirement/work item → store → retrieve shows modification",
        ],
        source_goal_ids=["g_demo_tool"],
        status="draft",
    )

    p.requirements["r_det_validation"] = Requirement(
        rid="r_det_validation",
        type="functional",
        statement="System provides deterministic internal consistency validation rules (e.g., required links exist; DAG is acyclic).",
        acceptance_criteria=[
            "Validator flags missing goal links on requirements",
            "Validator flags orphan uncertainties",
        ],
        source_goal_ids=["g_consistency"],
        status="draft",
    )

    # If a requirement creates a new blocker, add an uncertainty:
    # Example: “database” ambiguous (which one? local file ok? etc.)
    if "u_database_choice" not in p.uncertainties:
        p.uncertainties["u_database_choice"] = UncertaintyItem(
            uid="u_database_choice",
            kind="open_question",
            text="What persistence backend is acceptable for v1 demo: JSON file, SQLite, Postgres, or graph DB?",
            impact="high",
            blocks_progress=True,
            links=[
                Ref(type="requirement", id="r_persistence"),
                Ref(type="goal", id="g_demo_tool"),
            ],
        )

    # Validate + report
    issues = validate_project(p)
    print("\nValidation issues:")
    for i in issues:
        print("-", i)

    blockers = report_blocking_uncertainties(p)
    print("\nBlocking uncertainties:")
    for b in blockers:
        print(f"- {b.uid} [{b.impact}]: {b.text}")

    store.save_project(p)
    print("\nSaved updated project:", p.pid)

if __name__ == "__main__":
    main()