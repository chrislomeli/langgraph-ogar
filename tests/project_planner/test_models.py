"""
Pure unit tests for project engine domain models.

No database dependency.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from project_planner.models import (
    AcceptanceCriteria,
    Actor,
    ActorKind,
    Artifact,
    ArtifactKind,
    BlockerInfo,
    Event,
    MilestoneRollup,
    Note,
    Outcome,
    OutcomeState,
    Project,
    ProjectStatus,
    ProjectStatusReport,
    WorkItem,
    WorkItemKind,
    WorkItemState,
)


class TestEnums:

    def test_project_status_values(self):
        assert ProjectStatus.active == "active"
        assert ProjectStatus.archived == "archived"

    def test_work_item_kind_values(self):
        assert WorkItemKind.milestone == "milestone"
        assert WorkItemKind.task == "task"
        assert WorkItemKind.research == "research"
        assert WorkItemKind.decision == "decision"
        assert WorkItemKind.chore == "chore"

    def test_work_item_state_no_blocked(self):
        """blocked is computed, not stored — it should NOT be in the enum."""
        values = [s.value for s in WorkItemState]
        assert "blocked" not in values

    def test_work_item_state_values(self):
        expected = {"proposed", "planned", "active", "done", "canceled"}
        assert {s.value for s in WorkItemState} == expected

    def test_outcome_state_values(self):
        expected = {"pending", "verified", "failed", "waived"}
        assert {s.value for s in OutcomeState} == expected

    def test_actor_kind_values(self):
        assert ActorKind.human == "human"
        assert ActorKind.agent == "agent"

    def test_artifact_kind_values(self):
        expected = {"doc", "repo", "file", "url", "pr", "build", "design"}
        assert {k.value for k in ArtifactKind} == expected


class TestProject:

    def test_defaults(self):
        p = Project(name="Test")
        assert p.name == "Test"
        assert p.status == ProjectStatus.active
        assert p.id  # auto-generated
        assert isinstance(p.created_at, datetime)

    def test_explicit_id(self):
        p = Project(id="proj_1", name="Test")
        assert p.id == "proj_1"


class TestWorkItem:

    def test_minimal(self):
        w = WorkItem(project_id="p1", title="Do thing", kind=WorkItemKind.task)
        assert w.state == WorkItemState.proposed
        assert w.description is None
        assert w.priority is None
        assert w.acceptance is None

    def test_full(self):
        acc = AcceptanceCriteria(description="Tests pass")
        w = WorkItem(
            id="wi_1",
            project_id="p1",
            title="Build API",
            description="Implement the CRUD layer",
            kind=WorkItemKind.milestone,
            state=WorkItemState.active,
            priority=80,
            estimate_minutes=120,
            acceptance=acc,
        )
        assert w.id == "wi_1"
        assert w.description == "Implement the CRUD layer"
        assert w.acceptance.description == "Tests pass"
        assert w.acceptance.verified is False


class TestAcceptanceCriteria:

    def test_defaults(self):
        acc = AcceptanceCriteria(description="All tests green")
        assert acc.verified is False
        assert acc.verified_by is None
        assert acc.verified_at is None

    def test_verified(self):
        now = datetime.now(timezone.utc)
        acc = AcceptanceCriteria(
            description="All tests green",
            verified=True,
            verified_by="actor_chris",
            verified_at=now,
        )
        assert acc.verified is True
        assert acc.verified_by == "actor_chris"


class TestOutcome:

    def test_defaults(self):
        o = Outcome(project_id="p1", title="API works", criteria="Can CRUD")
        assert o.state == OutcomeState.pending


class TestArtifact:

    def test_with_project_id(self):
        a = Artifact(project_id="p1", kind=ArtifactKind.doc, ref="/docs/api.md")
        assert a.project_id == "p1"
        assert a.meta is None


class TestNote:

    def test_with_project_id(self):
        n = Note(project_id="p1", body="Remember to add indexes")
        assert n.project_id == "p1"
        assert n.tags == []

    def test_with_tags(self):
        n = Note(project_id="p1", body="Important", tags=["urgent", "schema"])
        assert n.tags == ["urgent", "schema"]


class TestActor:

    def test_human(self):
        a = Actor(kind=ActorKind.human, name="Chris")
        assert a.kind == ActorKind.human

    def test_agent(self):
        a = Actor(kind=ActorKind.agent, name="PlannerBot")
        assert a.kind == ActorKind.agent


class TestEvent:

    def test_defaults(self):
        e = Event(verb="WorkItemCreated")
        assert e.verb == "WorkItemCreated"
        assert e.payload == {}
        assert isinstance(e.ts, datetime)


class TestViewModels:

    def test_milestone_rollup(self):
        r = MilestoneRollup(
            milestone_id="m1", title="Schema", total=3, done=1, completion_ratio=0.333
        )
        assert r.completion_ratio == pytest.approx(0.333)

    def test_blocker_info(self):
        b = BlockerInfo(item_id="t1", item_title="Build API", blocked_by=["t2", "t3"])
        assert len(b.blocked_by) == 2

    def test_project_status_report(self):
        r = ProjectStatusReport(
            project_id="p1",
            project_name="Demo",
            milestones=[],
            outcomes=[],
        )
        assert r.project_name == "Demo"
