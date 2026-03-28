"""
Project-level CRUD for domain configurations.

A ``ProjectStore`` persists complete ``DomainConfig`` objects keyed by
project name.  The in-memory implementation (``InMemoryProjectStore``)
is suitable for tests and local development.  Swap it for a database-
backed implementation later without changing any call site.

Usage::

    from conversation_engine.storage.project_store import InMemoryProjectStore
    from conversation_engine.models.domain_config import DomainConfig

    store = InMemoryProjectStore()
    store.save(DomainConfig(project_name="acme", project_spec=spec, rules=rules))
    cfg = store.load("acme")
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Dict, List, Optional

from conversation_engine.storage import ProjectStore, snapshot_to_graph
from conversation_engine.storage.project_facade import project_to_graph

if TYPE_CHECKING:
    from conversation_engine.models.domain_config import DomainConfig


# ── Graph implementation ─────────────────────────────────────────

class GraphProjectStore(ProjectStore):
    """
    In-memory project store backed by a plain ``dict``.

    This implementation is suitable for tests and single-process use.
    It performs a shallow copy on save so that later mutations of the
    caller's objects do not silently alter stored data.
    """

    def __init__(self) -> None:
        self._store: Dict[str, DomainConfig] = {}

    def save(self, config: DomainConfig) -> None:
        if not config.project_name:
            raise ValueError("DomainConfig.project_name must not be empty")

        # project_name
        project_graph = project_to_graph(config)


        print(project_graph)











    def load(self, project_name: str) -> Optional[DomainConfig]:
        return self._store.get(project_name)

    def delete(self, project_name: str) -> bool:
        if project_name in self._store:
            del self._store[project_name]
            return True
        return False

    def list_projects(self) -> List[str]:
        return list(self._store.keys())

    def exists(self, project_name: str) -> bool:
        return project_name in self._store
