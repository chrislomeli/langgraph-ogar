"""
Domain models for the project engine.

Pure Pydantic v2 models — no database or framework dependencies.
These define the shape of data flowing through the system.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────


class ProjectStatus(str, Enum):
    active = "active"
    archived = "archived"


class WorkItemKind(str, Enum):
    milestone = "milestone"
    task = "task"
    research = "research"
    decision = "decision"
    chore = "chore"


class WorkItemState(str, Enum):
    proposed = "proposed"
    planned = "planned"
    active = "active"
    done = "done"
    canceled = "canceled"


class OutcomeState(str, Enum):
    pending = "pending"
    verified = "verified"
    failed = "failed"
    waived = "waived"


class ActorKind(str, Enum):
    human = "human"
    agent = "agent"


class ArtifactKind(str, Enum):
    doc = "doc"
    repo = "repo"
    file = "file"
    url = "url"
    pr = "pr"
    build = "build"
    design = "design"


# ── Helpers ────────────────────────────────────────────────────────


def _new_id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── Domain Models ──────────────────────────────────────────────────


class Project(BaseModel):
    id: str = Field(default_factory=_new_id)
    name: str
    status: ProjectStatus = ProjectStatus.active
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class AcceptanceCriteria(BaseModel):
    """Structured acceptance criteria stored as JSON in Memgraph."""
    description: str
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None


class WorkItem(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    title: str
    description: Optional[str] = None
    kind: WorkItemKind
    state: WorkItemState = WorkItemState.proposed
    priority: Optional[int] = None
    due_at: Optional[datetime] = None
    estimate_minutes: Optional[int] = None
    acceptance: Optional[AcceptanceCriteria] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Outcome(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    title: str
    criteria: str
    state: OutcomeState = OutcomeState.pending
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class Artifact(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    kind: ArtifactKind
    ref: str
    meta: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Note(BaseModel):
    id: str = Field(default_factory=_new_id)
    project_id: str
    body: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class Actor(BaseModel):
    id: str = Field(default_factory=_new_id)
    kind: ActorKind
    name: str


class Event(BaseModel):
    """Append-only audit record. Created automatically by commands."""
    id: str = Field(default_factory=_new_id)
    ts: datetime = Field(default_factory=_now)
    verb: str
    payload: dict[str, Any] = Field(default_factory=dict)
    # actor and target are expressed as edges, not properties


# ── View Models (returned by facade, not stored) ───────────────────


class MilestoneRollup(BaseModel):
    """Computed milestone progress."""
    milestone_id: str
    title: str
    total: int
    done: int
    completion_ratio: float


class BlockerInfo(BaseModel):
    """A work item and what blocks it."""
    item_id: str
    item_title: str
    blocked_by: list[str]


class ProjectStatusReport(BaseModel):
    """High-level project health."""
    project_id: str
    project_name: str
    milestones: list[MilestoneRollup]
    outcomes: list[Outcome]
