"""
MusicStore — same as M9, copied for self-contained milestone.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class ProjectRecord:
    """A saved project — all artifacts from a creation pipeline run."""
    title: str
    version: int
    saved_at: str
    sketch: Any
    plan: Any
    compile_result: Any


class MusicStore(abc.ABC):
    """Abstract persistence interface for musical projects."""

    @abc.abstractmethod
    def save(self, title: str, sketch: Any, plan: Any, compile_result: Any) -> ProjectRecord: ...

    @abc.abstractmethod
    def load(self, title: str, version: Optional[int] = None) -> ProjectRecord: ...

    @abc.abstractmethod
    def list_projects(self) -> list[dict]: ...

    @abc.abstractmethod
    def exists(self, title: str) -> bool: ...


class InMemoryStore(MusicStore):
    """Dict-backed implementation — holds full Python objects in memory."""

    def __init__(self):
        self._projects: dict[str, list[ProjectRecord]] = {}

    def save(self, title: str, sketch: Any, plan: Any, compile_result: Any) -> ProjectRecord:
        versions = self._projects.get(title, [])
        version = len(versions) + 1
        record = ProjectRecord(
            title=title, version=version,
            saved_at=datetime.now(timezone.utc).isoformat(),
            sketch=sketch, plan=plan, compile_result=compile_result,
        )
        if title not in self._projects:
            self._projects[title] = []
        self._projects[title].append(record)
        return record

    def load(self, title: str, version: Optional[int] = None) -> ProjectRecord:
        if title not in self._projects:
            raise KeyError(f"Project not found: '{title}'")
        versions = self._projects[title]
        if version is None:
            return versions[-1]
        for record in versions:
            if record.version == version:
                return record
        raise KeyError(f"Version {version} not found for '{title}'")

    def list_projects(self) -> list[dict]:
        result = []
        for title, versions in sorted(self._projects.items()):
            latest = versions[-1]
            result.append({
                "title": title, "versions": len(versions),
                "latest_version": latest.version, "saved_at": latest.saved_at,
            })
        return result

    def exists(self, title: str) -> bool:
        return title in self._projects
