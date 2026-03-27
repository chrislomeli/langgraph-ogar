"""
Domain configuration — everything a domain brings to the conversation engine.

A DomainConfig is a frozen value object that describes a complete project
configuration.  It is the single serialisation target for project-level
persistence: one ``DomainConfig`` ↔ one project in the store.

All fields are optional.  When a field is ``None`` the conversation graph
treats it as "not yet available" — a deterministic gather node can fill
the gap (ask the human, load from DB, etc.) without involving the LLM.

Usage::

    from conversation_engine.models.domain_config import DomainConfig

    cfg = DomainConfig(
        project_name="my-project",
        knowledge_graph=graph,
        rules=rules,
    )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from conversation_engine.models.queries import GraphQueryPattern
from conversation_engine.models.rules import IntegrityRule
from conversation_engine.models.validation_quiz import ValidationQuiz
from conversation_engine.storage import ProjectSpecification
from conversation_engine.storage.graph import KnowledgeGraph


@dataclass(frozen=True)
class DomainConfig:
    """
    Complete domain specification for a project.

    This is a pure value object — no behavior, no side-effects.
    The ``ConversationContext`` implementation *consumes* a DomainConfig;
    graph nodes *inspect* it to decide what still needs gathering.

    Attributes:
        project_name: Unique human-readable project identifier.
        knowledge_graph: The project's knowledge graph (nodes + edges).
        rules: Integrity rules the graph must satisfy.
        quiz: LLM pre-flight validation questions.
        query_patterns: Reusable graph query patterns for AI reasoning.
        system_prompt: The system prompt that teaches an LLM about this domain.
        metadata: Arbitrary extra data (version, owner, timestamps, etc.).
    """

    project_name: str
    knowledge_graph: Optional[KnowledgeGraph] = None  # todo - deprecate this
    project_specification: Optional[ProjectSpecification] = None
    rules: Optional[List[IntegrityRule]] = None
    quiz: Optional[List[ValidationQuiz]] = None
    query_patterns: Optional[List[GraphQueryPattern]] = None
    system_prompt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # # ── Convenience Methods ────────────────────────────────────────────

    def with_project_name(self, project_name: str) -> "DomainConfig":
        """Return a new DomainConfig with the project_name changed."""
        return DomainConfig(
            project_name=project_name,
            knowledge_graph=self.knowledge_graph,
            rules=self.rules,
            quiz=self.quiz,
            query_patterns=self.query_patterns,
            system_prompt=self.system_prompt,
            metadata=self.metadata,
        )

    # ── Serialisation ────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialise the full domain config to a JSON-safe dict.

        This is the payload that a ``ProjectStore`` writes to disk or DB.
        """
        return {
            "project_name": self.project_name,
            "knowledge_graph": (
                self.knowledge_graph.to_dict()
                if self.knowledge_graph is not None
                else None
            ),
            "rules": (
                [r.model_dump() for r in self.rules]
                if self.rules is not None
                else None
            ),
            "quiz": (
                [_quiz_to_dict(q) for q in self.quiz]
                if self.quiz is not None
                else None
            ),
            "query_patterns": (
                [p.model_dump() for p in self.query_patterns]
                if self.query_patterns is not None
                else None
            ),
            "system_prompt": self.system_prompt,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainConfig":
        """
        Reconstruct a DomainConfig from the dict produced by ``to_dict()``.
        """
        graph_data = data.get("knowledge_graph")
        rules_data = data.get("rules")
        quiz_data = data.get("quiz")
        patterns_data = data.get("query_patterns")

        return cls(
            project_name=data["project_name"],
            knowledge_graph=(
                KnowledgeGraph.from_dict(graph_data)
                if graph_data is not None
                else None
            ),
            rules=(
                [IntegrityRule.model_validate(r) for r in rules_data]
                if rules_data is not None
                else None
            ),
            quiz=(
                [_quiz_from_dict(q) for q in quiz_data]
                if quiz_data is not None
                else None
            ),
            query_patterns=(
                [GraphQueryPattern.model_validate(p) for p in patterns_data]
                if patterns_data is not None
                else None
            ),
            system_prompt=data.get("system_prompt"),
            metadata=data.get("metadata", {}),
        )


# ── ValidationQuiz dict helpers (dataclass, not Pydantic) ────────────

def _quiz_to_dict(q: ValidationQuiz) -> Dict[str, Any]:
    return {
        "question": q.question,
        "required_concepts": list(q.required_concepts),
        "prohibited_concepts": list(q.prohibited_concepts),
        "weight": q.weight,
        "min_score": q.min_score,
    }


def _quiz_from_dict(d: Dict[str, Any]) -> ValidationQuiz:
    return ValidationQuiz(
        question=d["question"],
        required_concepts=d["required_concepts"],
        prohibited_concepts=d.get("prohibited_concepts", []),
        weight=d.get("weight", 1.0),
        min_score=d.get("min_score", 0.5),
    )
