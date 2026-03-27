"""
ProjectService Protocol — the single gateway for all project operations.

Both LLM tools and deterministic code nodes call the same interface.
The service owns:
  - Persistence (load / save / delete)
  - Validation (run integrity rules, produce Findings)
  - Spec conversion (ProjectSnapshot ↔ KnowledgeGraph)
  - Finding formatting (business-level text summaries)
  - System prompt + preflight quiz (domain-specific LLM configuration)

Design principles:
  - Protocol, not ABC — structural subtyping, no inheritance required
  - Input/output is always ProjectSnapshot + Finding — never raw graph
  - The KnowledgeGraph is an internal implementation detail
  - @runtime_checkable for isinstance() checks
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Protocol, runtime_checkable

from conversation_engine.graph.context import Finding, ValidationResult
from conversation_engine.models.validation_quiz import ValidationQuiz
from conversation_engine.storage.project_specification import ProjectSpecification


Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ProjectServiceResult:
    """
    Result envelope for service operations.

    Provides a uniform ok/error pattern for all service methods.
    """
    success: bool
    message: str = ""
    snapshot: Optional[ProjectSpecification] = None
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ProjectService(Protocol):
    """
    The single interface for all project operations.

    Both LLM tools and deterministic code nodes call this.
    Implementations hold all domain-specific internals (graph, rules,
    evaluator, store) behind this boundary.
    """

    def get(self, project_name: str) -> ProjectServiceResult:
        """
        Load a project by name, returned as a ProjectSnapshot.

        Returns success=False if the project does not exist.
        """
        ...

    def save(self, spec: ProjectSpecification) -> ProjectServiceResult:
        """
        Persist a project from a ProjectSnapshot.

        Validates the spec, converts to internal representation,
        runs integrity rules, and persists.  Returns the validation
        findings in the result (even on success — they are informational).
        """
        ...

    def validate(self, project_name: str) -> ProjectServiceResult:
        """
        Run integrity validation on a stored project.

        Returns findings describing any gaps or violations.
        """
        ...

    def delete(self, project_name: str) -> ProjectServiceResult:
        """
        Delete a project by name.

        Returns success=False if the project does not exist.
        """
        ...

    def exists(self, project_name: str) -> bool:
        """Check whether a project exists."""
        ...

    def list_projects(self) -> List[str]:
        """Return all stored project names."""
        ...

    def format_finding_summary(self, findings: List[Finding]) -> str:
        """
        Produce a human-readable summary of findings.

        The domain controls the language — the caller (loop or LLM)
        never needs to know about graph concepts.
        """
        ...

    @property
    def system_prompt(self) -> str:
        """The system prompt that teaches an LLM about this domain."""
        ...

    @property
    def preflight_quiz(self) -> List[ValidationQuiz]:
        """
        Quiz questions for pre-run LLM validation.

        Return an empty list to skip pre-flight validation.
        """
        ...
