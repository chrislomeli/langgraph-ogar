"""
ToolResultEnvelope — Every tool call returns its payload wrapped in metadata.

Now MCP-faithful:
  - content: MCP-style ContentBlock[]
  - structured: optional structured payload (maps to MCP structuredContent)
  - is_error: tool-level failure indicator (maps to MCP isError)

Still JSON-serializable and easy to embed in state dicts.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolContentBlock(BaseModel):
    """
    Minimal MCP-compatible content block.

    Expand later if you want images/audio/etc.
    """
    type: Literal["text"] = "text"
    text: str


class ToolResultMeta(BaseModel):
    """Metadata about a tool invocation. Attached to every result."""

    tool_name: str
    tool_description: str = ""
    input_args: dict[str, Any]
    input_hash: str = Field(
        default="",
        description="SHA-256 hex digest of canonical JSON input — for dedup/caching",
    )
    timestamp: float = Field(
        default_factory=time.time,
        description="Unix timestamp when the call completed",
    )
    duration_ms: float = Field(
        default=0.0,
        description="Wall-clock execution time in milliseconds",
    )
    success: bool = True
    error: str | None = None

    @staticmethod
    def hash_args(args: dict[str, Any]) -> str:
        """
        Deterministic-ish hash of input args for caching/dedup.
        Prefer hashing validated_input JSON in the client for true determinism.
        """
        canonical = json.dumps(args, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class ToolResultEnvelope(BaseModel):
    """
    Wraps every tool result with provenance metadata.

    - content: MCP-like content blocks (always present)
    - structured: optional structured payload
    - is_error: tool-level error marker
    """

    meta: ToolResultMeta
    content: list[ToolContentBlock] = Field(default_factory=list)
    structured: dict[str, Any] | None = None
    is_error: bool = False

    # Backwards-compat alias if you have existing code referencing .payload
    @property
    def payload(self) -> dict[str, Any]:
        return self.structured or {}

    def model_dump_flat(self) -> dict[str, Any]:
        """
        Return structured payload with _meta key injected — for embedding in state dicts.
        If structured is None, returns just _meta.
        """
        base = self.structured or {}
        return {**base, "_meta": self.meta.model_dump()}
