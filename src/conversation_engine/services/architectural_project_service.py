"""
ArchitecturalProjectService — concrete ProjectService for the architectural
ontology domain.

This implementation backs the service with:
  - A ``ProjectStore`` for persistence (InMemory, File, future Memgraph)
  - The snapshot facade for ProjectSnapshot ↔ KnowledgeGraph conversion
  - ``RuleEvaluator`` + ``IntegrityRule`` for deterministic validation
  - Domain-specific finding formatting and system prompt

The KnowledgeGraph is an internal detail — callers only see
``ProjectSnapshot`` and ``Finding``.
"""
from __future__ import annotations

import uuid
import logging
from typing import Dict, List, Optional

from conversation_engine.graph.context import Finding, ValidationResult
from conversation_engine.models.domain_config import DomainConfig
from conversation_engine.models.rules import IntegrityRule
from conversation_engine.models.validation_quiz import ValidationQuiz
from conversation_engine.storage.graph import KnowledgeGraph
from conversation_engine.storage.project_store import ProjectStore
from conversation_engine.storage.project_specification import ProjectSpecification
from conversation_engine.storage.project_graph_facade import (
    snapshot_to_graph,
    graph_to_snapshot,
    SnapshotConversionError,
)
from conversation_engine.validation.evaluator import RuleEvaluator
from conversation_engine.infrastructure.llm.architectural_quiz import (
    ARCHITECTURAL_SYSTEM_PROMPT,
    ARCHITECTURAL_QUIZ,
)
from conversation_engine.services.project_service import ProjectServiceResult

logger = logging.getLogger(__name__)


# ── Finding-type mapping ───────────────────────────────────────────

_RULE_ID_TO_FINDING_TYPE: Dict[str, str] = {
    "rule-goal-req": "missing_goal_coverage",
    "rule-req-cap": "missing_requirement_realization",
    "rule-cap-comp": "missing_capability_realization",
    "rule-comp-dep": "missing_component_dependencies",
}


def _default_finding_type(rule_id: str) -> str:
    return _RULE_ID_TO_FINDING_TYPE.get(rule_id, "missing_goal_coverage")


class ArchitecturalProjectService:
    """
    ProjectService implementation for the architectural ontology domain.

    Satisfies the ``ProjectService`` protocol via structural subtyping.
    """

    def __init__(
        self,
        store: ProjectStore,
        rules: Optional[List[IntegrityRule]] = None,
        system_prompt_override: Optional[str] = None,
        quiz_override: Optional[List[ValidationQuiz]] = None,
    ) -> None:
        self._store = store
        self._rules = rules or []
        self._system_prompt_override = system_prompt_override
        self._quiz_override = quiz_override

    # ── CRUD ──────────────────────────────────────────────────────

    def get(self, project_name: str) -> ProjectServiceResult:
        config = self._store.load(project_name)
        if config is None:
            return ProjectServiceResult(
                success=False,
                message=f"Project '{project_name}' not found.",
            )
        if config.knowledge_graph is None:
            return ProjectServiceResult(
                success=True,
                message=f"Project '{project_name}' exists but has no knowledge graph.",
                snapshot=ProjectSpecification(project_name=project_name),
            )
        snapshot = graph_to_snapshot(project_name, config.knowledge_graph)
        return ProjectServiceResult(
            success=True,
            message=f"Project '{project_name}' loaded.",
            snapshot=snapshot,
        )

    def save(self, spec: ProjectSpecification) -> ProjectServiceResult:
        try:
            graph = snapshot_to_graph(spec)
        except SnapshotConversionError as e:
            return ProjectServiceResult(
                success=False,
                message=f"Invalid spec: {e}",
            )

        # Merge rules from existing config if present
        existing = self._store.load(spec.project_name)
        existing_rules = existing.rules if existing else None

        config = DomainConfig(
            project_name=spec.project_name,
            knowledge_graph=graph,
            rules=existing_rules or self._rules or None,
            quiz=self._quiz_override,
            system_prompt=self._system_prompt_override,
        )
        self._store.save(config)

        # Run validation on the newly saved graph
        findings = self._evaluate_graph(graph)

        return ProjectServiceResult(
            success=True,
            message=(
                f"Project '{spec.project_name}' saved "
                f"({graph.node_count()} nodes, {graph.edge_count()} edges). "
                f"{len(findings)} finding(s)."
            ),
            snapshot=spec,
            findings=findings,
        )

    def validate(self, project_name: str) -> ProjectServiceResult:
        config = self._store.load(project_name)
        if config is None:
            return ProjectServiceResult(
                success=False,
                message=f"Project '{project_name}' not found.",
            )
        graph = config.knowledge_graph or KnowledgeGraph()
        rules = config.rules or self._rules or []
        findings = self._evaluate_graph(graph, rules)

        return ProjectServiceResult(
            success=True,
            message=self.format_finding_summary(findings),
            findings=findings,
        )

    def delete(self, project_name: str) -> ProjectServiceResult:
        removed = self._store.delete(project_name)
        if removed:
            return ProjectServiceResult(
                success=True,
                message=f"Project '{project_name}' deleted.",
            )
        return ProjectServiceResult(
            success=False,
            message=f"Project '{project_name}' not found.",
        )

    def exists(self, project_name: str) -> bool:
        return self._store.exists(project_name)

    def list_projects(self) -> List[str]:
        return self._store.list_projects()

    # ── Validation ────────────────────────────────────────────────

    def validate_findings(
        self,
        project_name: str,
        prior_findings: Optional[List[Finding]] = None,
    ) -> ValidationResult:
        """
        Run validation and return a ValidationResult (preserving resolved findings).

        This is the method the conversation loop's validate node calls.
        It mirrors the old ConversationContext.validate() signature.
        """
        prior = prior_findings or []
        config = self._store.load(project_name)
        if config is None:
            return ValidationResult(findings=prior)

        graph = config.knowledge_graph or KnowledgeGraph()
        rules = config.rules or self._rules or []

        evaluator = RuleEvaluator(graph)
        violations = evaluator.evaluate_all_rules(rules)

        # Preserve resolved findings from prior turns
        resolved = [f for f in prior if f.resolved]

        new_findings: List[Finding] = []
        for v in violations:
            new_findings.append(
                Finding(
                    id=f"finding-{uuid.uuid4().hex[:8]}",
                    finding_type=_default_finding_type(v.rule_id),
                    severity=v.severity,
                    subject_ids=[v.node_id],
                    message=v.message,
                    evidence=[f"Expected {v.expected_count}, found {v.actual_count}"],
                    related_rule_ids=[v.rule_id],
                )
            )

        return ValidationResult(findings=resolved + new_findings)

    # ── Formatting ────────────────────────────────────────────────

    def format_finding_summary(self, findings: List[Finding]) -> str:
        if not findings:
            return (
                "All integrity checks pass. "
                "The knowledge graph looks complete."
            )
        lines = [f"Found {len(findings)} issue(s):"]
        for f in findings:
            lines.append(f"  [{f.severity}] {f.message}")
        return "\n".join(lines)

    # ── Domain configuration ─────────────────────────────────────

    @property
    def system_prompt(self) -> str:
        return self._system_prompt_override or ARCHITECTURAL_SYSTEM_PROMPT

    @property
    def preflight_quiz(self) -> List[ValidationQuiz]:
        if self._quiz_override is not None:
            return list(self._quiz_override)
        return list(ARCHITECTURAL_QUIZ)

    # ── Internal ──────────────────────────────────────────────────

    def _evaluate_graph(
        self,
        graph: KnowledgeGraph,
        rules: Optional[List[IntegrityRule]] = None,
    ) -> List[Finding]:
        """Run RuleEvaluator and return Findings."""
        use_rules = rules if rules is not None else self._rules
        if not use_rules:
            return []
        evaluator = RuleEvaluator(graph)
        violations = evaluator.evaluate_all_rules(use_rules)
        findings: List[Finding] = []
        for v in violations:
            findings.append(
                Finding(
                    id=f"finding-{uuid.uuid4().hex[:8]}",
                    finding_type=_default_finding_type(v.rule_id),
                    severity=v.severity,
                    subject_ids=[v.node_id],
                    message=v.message,
                    evidence=[f"Expected {v.expected_count}, found {v.actual_count}"],
                    related_rule_ids=[v.rule_id],
                )
            )
        return findings
