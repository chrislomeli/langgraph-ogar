"""
MusicStore — persistence abstraction for musical artifacts.

KEY CONCEPT: This ABC defines the contract for save/load/list operations.
Nodes call store.save() / store.load() / store.list_projects() without
knowing whether the backend is a dict, SQLite, or Memgraph.

The store holds FULL Python objects — Sketch, PlanBundle, CompileResult.
This keeps serialization concerns out of the graph nodes.

Implementations:
  - InMemoryStore: dict-backed, for testing and learning
  - Future: MemgraphStore wrapping GraphMusicWriter/Reader
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class ProjectRecord:
    """A saved project — all artifacts from a creation pipeline run.

    Note: music21 Score is NOT stored — it's rendered on demand
    from compile_result when needed for presentation.
    """
    title: str
    version: int
    saved_at: str
    sketch: Any           # Sketch
    plan: Any             # PlanBundle
    compile_result: Any   # CompileResult


class MusicStore(abc.ABC):
    """
    Abstract persistence interface for musical projects.

    Graph nodes receive a store instance via dependency injection
    and call these methods. The implementation can be swapped
    without changing any node code.
    """

    @abc.abstractmethod
    def save(
        self,
        title: str,
        sketch: Any,
        plan: Any,
        compile_result: Any,
    ) -> ProjectRecord:
        """Save a project. Auto-increments version if title exists."""
        ...

    @abc.abstractmethod
    def load(self, title: str, version: Optional[int] = None) -> ProjectRecord:
        """Load a project by title. Latest version if version is None."""
        ...

    @abc.abstractmethod
    def list_projects(self) -> list[dict]:
        """List all saved projects with title, version, saved_at."""
        ...

    @abc.abstractmethod
    def exists(self, title: str) -> bool:
        """Check if a project with this title exists."""
        ...


class InMemoryStore(MusicStore):
    """
    Dict-backed implementation — holds full Python objects in memory.

    Structure:
        _projects[title] = [ProjectRecord(v1), ProjectRecord(v2), ...]

    This is the learning/testing implementation. Replace with
    MemgraphStore for production persistence.
    """

    def __init__(self):
        self._projects: dict[str, list[ProjectRecord]] = {}

    def save(
        self,
        title: str,
        sketch: Any,
        plan: Any,
        compile_result: Any,
    ) -> ProjectRecord:
        """Save a project. Auto-increments version."""
        versions = self._projects.get(title, [])
        version = len(versions) + 1

        record = ProjectRecord(
            title=title,
            version=version,
            saved_at=datetime.now(timezone.utc).isoformat(),
            sketch=sketch,
            plan=plan,
            compile_result=compile_result,
        )

        if title not in self._projects:
            self._projects[title] = []
        self._projects[title].append(record)

        return record

    def load(self, title: str, version: Optional[int] = None) -> ProjectRecord:
        """Load a project. Latest version if version is None."""
        if title not in self._projects:
            raise KeyError(f"Project not found: '{title}'")

        versions = self._projects[title]

        if version is None:
            return versions[-1]  # Latest

        for record in versions:
            if record.version == version:
                return record

        raise KeyError(f"Version {version} not found for '{title}'")

    def list_projects(self) -> list[dict]:
        """List all projects with latest version info."""
        result = []
        for title, versions in sorted(self._projects.items()):
            latest = versions[-1]
            result.append({
                "title": title,
                "versions": len(versions),
                "latest_version": latest.version,
                "saved_at": latest.saved_at,
            })
        return result

    def exists(self, title: str) -> bool:
        return title in self._projects
