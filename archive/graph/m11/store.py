"""
MusicStore -- same as M10, copied for self-contained milestone.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class ProjectRecord:
    title: str
    version: int
    saved_at: str
    sketch: Any
    plan: Any
    compile_result: Any


class MusicStore(abc.ABC):
    @abc.abstractmethod
    def save(self, title: str, sketch: Any, plan: Any, compile_result: Any) -> ProjectRecord: ...
    @abc.abstractmethod
    def load(self, title: str, version: Optional[int] = None) -> ProjectRecord: ...
    @abc.abstractmethod
    def list_projects(self) -> list[dict]: ...
    @abc.abstractmethod
    def exists(self, title: str) -> bool: ...


class InMemoryStore(MusicStore):
    def __init__(self):
        self._projects: dict[str, list[ProjectRecord]] = {}

    def save(self, title, sketch, plan, compile_result):
        versions = self._projects.get(title, [])
        version = len(versions) + 1
        record = ProjectRecord(
            title=title, version=version,
            saved_at=datetime.now(timezone.utc).isoformat(),
            sketch=sketch, plan=plan, compile_result=compile_result,
        )
        self._projects.setdefault(title, []).append(record)
        return record

    def load(self, title, version=None):
        if title not in self._projects:
            raise KeyError(f"Project not found: '{title}'")
        versions = self._projects[title]
        if version is None:
            return versions[-1]
        for record in versions:
            if record.version == version:
                return record
        raise KeyError(f"Version {version} not found for '{title}'")

    def list_projects(self):
        result = []
        for title, versions in sorted(self._projects.items()):
            latest = versions[-1]
            result.append({"title": title, "versions": len(versions),
                           "latest_version": latest.version, "saved_at": latest.saved_at})
        return result

    def exists(self, title):
        return title in self._projects
