from starter.model.project import Project, Goal, Requirement, UncertaintyItem, Ref
from starter.engine import validate_project, report_blocking_uncertainties
from starter.store import JsonFileProjectStore

def test_project_round_trip(tmp_path):
    store = JsonFileProjectStore(tmp_path)

    p = Project(
        pid="p1",
        title="Test Project",
        non_goals=["Not a sellable product"],
    )
    p.goals["g1"] = Goal(gid="g1", statement="Build demo", success_metrics=["demo runs"], priority=0)
    p.requirements["r1"] = Requirement(
        rid="r1",
        type="functional",
        statement="Persist and reload project",
        acceptance_criteria=["save then load yields equivalent object"],
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

    store.save_project(p)
    loaded = store.load_project("p1")

    # Basic structural equality checks
    assert loaded.pid == p.pid
    assert loaded.title == p.title
    assert set(loaded.goals.keys()) == set(p.goals.keys())
    assert loaded.goals["g1"].statement == p.goals["g1"].statement
    assert loaded.requirements["r1"].source_goal_ids == ["g1"]

    # Validate after reload
    issues = validate_project(loaded)
    # Expect no errors (warnings are fine depending on your policy)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == []

    # Report check
    blockers = report_blocking_uncertainties(loaded)
    assert [b.uid for b in blockers] == ["u1"]