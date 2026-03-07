"""
Shared fixtures for project engine integration tests.

Requires a running Memgraph instance.
Tests are skipped if Memgraph is not available.
"""

from __future__ import annotations

import pytest
from gqlalchemy import Memgraph

from project_planner.persistence.connection import get_memgraph, ensure_schema
from project_planner.persistence.commands import create_actor


def _memgraph_available() -> bool:
    try:
        db = get_memgraph()
        db.execute("RETURN 1")
        return True
    except Exception:
        return False


requires_memgraph = pytest.mark.skipif(
    not _memgraph_available(),
    reason="Memgraph not available",
)


@pytest.fixture
def db():
    """
    Provide a clean Memgraph connection for each test.

    Wipes all data before and after each test.
    """
    mg = get_memgraph()
    mg.execute("MATCH (n) DETACH DELETE n")
    ensure_schema(mg)
    yield mg
    mg.execute("MATCH (n) DETACH DELETE n")


@pytest.fixture
def actor_id(db):
    """Create a default test actor and return its id."""
    return create_actor(db, id="actor_test", kind="human", name="Test User")
