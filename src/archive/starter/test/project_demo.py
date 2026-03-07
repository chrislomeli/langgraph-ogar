from starter.model.project import Project, Goal, Requirement, UncertaintyItem, Ref
from starter.engine import validate_project, report_blocking_uncertainties

p = Project(pid="p1", title="Agentic Planner")
p.goals["g1"] = Goal(gid="g1", statement="Build demo tool", success_metrics=["demo runs"], priority=0)
p.requirements["r1"] = Requirement(
    rid="r1",
    type="functional",
    statement="Persist and reload project plan",
    acceptance_criteria=["store then load yields same object"],
    source_goal_ids=["g1"],
)
p.uncertainties["u1"] = UncertaintyItem(
    uid="u1",
    kind="open_question",
    text="CLI or API?",
    impact="high",
    blocks_progress=True,
    links=[Ref(type="goal", id="g1"), Ref(type="requirement", id="r1")],
)

issues = validate_project(p)
print("Issues:", issues)
print("Blockers:", report_blocking_uncertainties(p))