"""
Tests for ProjectService — the single gateway for all project operations.

Covers:
- Protocol conformance (ArchitecturalProjectService satisfies ProjectService)
- CRUD: get, save, delete, exists, list_projects
- Validation: validate, validate_findings
- Finding formatting
- System prompt and preflight quiz
- Save validates spec (bad refs → failure)
- Save returns findings (informational)
- Round-trip: save → get preserves data
- validate_findings preserves resolved findings
"""
from __future__ import annotations

import pytest

from conversation_engine.services.project_service import (
    ProjectService,
    ProjectServiceResult,
)
from conversation_engine.services.architectural_project_service import (
    ArchitecturalProjectService,
)
from conversation_engine.graph.context import Finding
from conversation_engine.models.rules import IntegrityRule
from conversation_engine.storage.project_store import InMemoryProjectStore
from conversation_engine.storage.snapshot import (
    ProjectSnapshot,
    GoalSpec,
    RequirementSpec,
    CapabilitySpec,
    ComponentSpec,
    ConstraintSpec,
    DependencySpec,
)


# ── Helpers ────────────────────────────────────────────────────────

def _goal_req_rule() -> IntegrityRule:
    return IntegrityRule(
        id="rule-goal-req",
        name="Goal → Requirement",
        description="Every goal must have at least one requirement",
        applies_to_node_type="goal",
        rule_type="minimum_outgoing_edge_count",
        edge_type="SATISFIED_BY",
        target_node_types=["requirement"],
        minimum_count=1,
        severity="high",
        failure_message_template="Goal '{subject_name}' has no requirements.",
    )


def _req_cap_rule() -> IntegrityRule:
    return IntegrityRule(
        id="rule-req-cap",
        name="Requirement → Capability",
        description="Every requirement must have at least one capability",
        applies_to_node_type="requirement",
        rule_type="minimum_outgoing_edge_count",
        edge_type="REALIZED_BY",
        target_node_types=["capability"],
        minimum_count=1,
        severity="medium",
        failure_message_template="Requirement '{subject_name}' has no capabilities.",
    )


def _sample_snapshot() -> ProjectSnapshot:
    return ProjectSnapshot(
        project_name="acme",
        goals=[
            GoalSpec(name="User Auth", statement="Users can log in"),
        ],
        requirements=[
            RequirementSpec(name="OAuth", goal_ref="User Auth", requirement_type="functional"),
        ],
        capabilities=[
            CapabilitySpec(name="SSO", requirement_refs=["OAuth"]),
        ],
        components=[
            ComponentSpec(name="Auth Service", capability_refs=["SSO"]),
        ],
        constraints=[
            ConstraintSpec(name="GDPR", statement="Must comply"),
        ],
        dependencies=[
            DependencySpec(name="Redis", description="Cache"),
        ],
    )


def _snapshot_with_gaps() -> ProjectSnapshot:
    """A snapshot where Goal 'Orphan' has no requirements → violation."""
    return ProjectSnapshot(
        project_name="gaps",
        goals=[
            GoalSpec(name="Connected", statement="Has reqs"),
            GoalSpec(name="Orphan", statement="No reqs"),
        ],
        requirements=[
            RequirementSpec(name="R1", goal_ref="Connected"),
        ],
    )


def _make_service(rules=None) -> ArchitecturalProjectService:
    store = InMemoryProjectStore()
    return ArchitecturalProjectService(
        store=store,
        rules=rules or [_goal_req_rule(), _req_cap_rule()],
    )


# ── Protocol conformance ─────────────────────────────────────────

class TestProtocolConformance:

    def test_satisfies_protocol(self):
        svc = _make_service()
        assert isinstance(svc, ProjectService)


# ── CRUD: save + get ─────────────────────────────────────────────

class TestSaveAndGet:

    def test_save_success(self):
        svc = _make_service()
        result = svc.save(_sample_snapshot())
        assert result.success is True
        assert "saved" in result.message.lower()
        assert result.snapshot is not None
        assert result.snapshot.project_name == "acme"

    def test_save_then_get(self):
        svc = _make_service()
        svc.save(_sample_snapshot())
        result = svc.get("acme")
        assert result.success is True
        assert result.snapshot is not None
        assert result.snapshot.project_name == "acme"
        assert len(result.snapshot.goals) == 1
        assert result.snapshot.goals[0].name == "User Auth"

    def test_save_round_trip_preserves_refs(self):
        svc = _make_service()
        svc.save(_sample_snapshot())
        result = svc.get("acme")
        snap = result.snapshot
        assert snap.requirements[0].goal_ref == "User Auth"
        assert snap.capabilities[0].requirement_refs == ["OAuth"]
        assert snap.components[0].capability_refs == ["SSO"]

    def test_save_overwrites_existing(self):
        svc = _make_service()
        svc.save(_sample_snapshot())

        updated = _sample_snapshot()
        updated.goals.append(GoalSpec(name="New Goal", statement="Added"))
        updated.requirements.append(RequirementSpec(name="New Req", goal_ref="New Goal"))
        svc.save(updated)

        result = svc.get("acme")
        assert len(result.snapshot.goals) == 2

    def test_save_bad_ref_fails(self):
        svc = _make_service()
        bad = ProjectSnapshot(
            project_name="bad",
            requirements=[RequirementSpec(name="R", goal_ref="NoGoal")],
        )
        result = svc.save(bad)
        assert result.success is False
        assert "invalid spec" in result.message.lower()

    def test_save_returns_findings(self):
        svc = _make_service()
        result = svc.save(_snapshot_with_gaps())
        assert result.success is True
        assert len(result.findings) > 0
        # Should find the orphan goal violation
        messages = [f.message for f in result.findings]
        assert any("Orphan" in m for m in messages)

    def test_get_not_found(self):
        svc = _make_service()
        result = svc.get("nonexistent")
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_save_empty_snapshot(self):
        svc = _make_service()
        result = svc.save(ProjectSnapshot(project_name="empty"))
        assert result.success is True


# ── CRUD: delete ─────────────────────────────────────────────────

class TestDelete:

    def test_delete_existing(self):
        svc = _make_service()
        svc.save(_sample_snapshot())
        result = svc.delete("acme")
        assert result.success is True
        assert not svc.exists("acme")

    def test_delete_not_found(self):
        svc = _make_service()
        result = svc.delete("nonexistent")
        assert result.success is False


# ── CRUD: exists + list ──────────────────────────────────────────

class TestExistsAndList:

    def test_exists_false_initially(self):
        svc = _make_service()
        assert svc.exists("acme") is False

    def test_exists_true_after_save(self):
        svc = _make_service()
        svc.save(_sample_snapshot())
        assert svc.exists("acme") is True

    def test_list_empty(self):
        svc = _make_service()
        assert svc.list_projects() == []

    def test_list_after_save(self):
        svc = _make_service()
        svc.save(_sample_snapshot())
        assert "acme" in svc.list_projects()


# ── Validation ───────────────────────────────────────────────────

class TestValidation:

    def test_validate_complete_project(self):
        svc = _make_service(rules=[_goal_req_rule()])
        svc.save(_sample_snapshot())
        result = svc.validate("acme")
        assert result.success is True
        # Sample snapshot has Goal→Req, so goal_req_rule should pass
        goal_findings = [f for f in result.findings if f.finding_type == "missing_goal_coverage"]
        assert len(goal_findings) == 0

    def test_validate_project_with_gaps(self):
        svc = _make_service(rules=[_goal_req_rule()])
        svc.save(_snapshot_with_gaps())
        result = svc.validate("gaps")
        assert result.success is True
        assert len(result.findings) > 0
        messages = [f.message for f in result.findings]
        assert any("Orphan" in m for m in messages)

    def test_validate_not_found(self):
        svc = _make_service()
        result = svc.validate("nonexistent")
        assert result.success is False

    def test_validate_findings_preserves_resolved(self):
        svc = _make_service(rules=[_goal_req_rule()])
        svc.save(_snapshot_with_gaps())

        resolved = Finding(
            id="old-resolved",
            finding_type="missing_goal_coverage",
            severity="high",
            subject_ids=["goal-99"],
            message="Already fixed",
            resolved=True,
        )
        vr = svc.validate_findings("gaps", prior_findings=[resolved])
        ids = [f.id for f in vr.findings]
        assert "old-resolved" in ids

    def test_validate_findings_project_not_found_returns_prior(self):
        svc = _make_service()
        prior = [
            Finding(id="f1", finding_type="x", severity="low",
                    subject_ids=[], message="old")
        ]
        vr = svc.validate_findings("nonexistent", prior_findings=prior)
        assert len(vr.findings) == 1
        assert vr.findings[0].id == "f1"


# ── Formatting ───────────────────────────────────────────────────

class TestFormatting:

    def test_no_findings_positive_message(self):
        svc = _make_service()
        msg = svc.format_finding_summary([])
        assert "pass" in msg.lower() or "complete" in msg.lower()

    def test_with_findings_lists_issues(self):
        svc = _make_service()
        findings = [
            Finding(id="f1", finding_type="x", severity="high",
                    subject_ids=[], message="Something is wrong"),
        ]
        msg = svc.format_finding_summary(findings)
        assert "1 issue" in msg
        assert "Something is wrong" in msg


# ── Domain config ────────────────────────────────────────────────

class TestDomainConfig:

    def test_system_prompt_default(self):
        svc = _make_service()
        assert len(svc.system_prompt) > 0

    def test_system_prompt_override(self):
        svc = ArchitecturalProjectService(
            store=InMemoryProjectStore(),
            system_prompt_override="Custom prompt",
        )
        assert svc.system_prompt == "Custom prompt"

    def test_preflight_quiz_default(self):
        svc = _make_service()
        assert len(svc.preflight_quiz) > 0

    def test_preflight_quiz_override(self):
        from conversation_engine.models.validation_quiz import ValidationQuiz
        custom = [ValidationQuiz(question="Q?", required_concepts=["A"])]
        svc = ArchitecturalProjectService(
            store=InMemoryProjectStore(),
            quiz_override=custom,
        )
        assert len(svc.preflight_quiz) == 1
        assert svc.preflight_quiz[0].question == "Q?"


# ── Full lifecycle ───────────────────────────────────────────────

class TestFullLifecycle:
    """Simulate the real conversation flow: save → validate → fix → validate again."""

    def test_save_validate_fix_validate(self):
        svc = _make_service(rules=[_goal_req_rule()])

        # 1. Save project with gaps
        svc.save(_snapshot_with_gaps())

        # 2. Validate — should find orphan goal
        result = svc.validate("gaps")
        assert len(result.findings) > 0
        orphan_findings = [f for f in result.findings if "Orphan" in f.message]
        assert len(orphan_findings) == 1

        # 3. Fix — save updated spec with requirement for orphan goal
        fixed = ProjectSnapshot(
            project_name="gaps",
            goals=[
                GoalSpec(name="Connected", statement="Has reqs"),
                GoalSpec(name="Orphan", statement="Now has reqs"),
            ],
            requirements=[
                RequirementSpec(name="R1", goal_ref="Connected"),
                RequirementSpec(name="R2", goal_ref="Orphan"),
            ],
        )
        svc.save(fixed)

        # 4. Validate again — orphan goal should be gone
        result = svc.validate("gaps")
        orphan_findings = [f for f in result.findings if "Orphan" in f.message]
        assert len(orphan_findings) == 0
