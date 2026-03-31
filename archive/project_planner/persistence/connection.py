"""
Memgraph connection helper for the project engine.

Usage:
    db = get_memgraph()
    db.execute("MATCH (n) RETURN n LIMIT 1")

    # Or with custom host/port:
    db = get_memgraph(host="localhost", port=7688)
"""

from __future__ import annotations

import os
from pathlib import Path

from gqlalchemy import Memgraph


def get_memgraph(
    host: str | None = None,
    port: int | None = None,
) -> Memgraph:
    """
    Create a Memgraph connection.

    Reads from environment variables if not provided:
      MEMGRAPH_HOST (default: "127.0.0.1")
      MEMGRAPH_PORT (default: 7687)
    """
    host = host or os.environ.get("MEMGRAPH_HOST", "127.0.0.1")
    port = port or int(os.environ.get("MEMGRAPH_PORT", "7687"))
    return Memgraph(host=host, port=port)


def ensure_schema(db: Memgraph) -> None:
    """Run the schema.cypher file to create indexes."""
    schema_path = Path(__file__).parent / "schema.cypher"
    text = schema_path.read_text()
    for line in text.strip().splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            db.execute(line)
