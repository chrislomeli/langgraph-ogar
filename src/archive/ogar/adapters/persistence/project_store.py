from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ogar.domain.models.project import Project


class ProjectStore(Protocol):
    def load_project(self, pid: str) -> Project: ...
    def save_project(self, project: Project) -> None: ...


class JsonFileProjectStore:
    """
    Minimal local persistence for learning + demo.

    Storage layout:
      <root>/<pid>.json

    Later you can replace this with Postgres/Memgraph without changing callers.
    """
    def __init__(self, root_dir: str | Path):
        self.root = Path(root_dir)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, pid: str) -> Path:
        return self.root / f"{pid}.json"

    def load_project(self, pid: str) -> Project:
        p = self._path(pid)
        if not p.exists():
            raise FileNotFoundError(f"Project not found: {p}")
        data = p.read_text(encoding="utf-8")
        # Pydantic v2:
        return Project.model_validate_json(data)

    def save_project(self, project: Project) -> None:
        p = self._path(project.pid)
        p.write_text(
            project.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )