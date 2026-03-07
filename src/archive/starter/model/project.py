from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator


# ---- Graph-friendly reference ----
ObjType = Literal["project", "goal", "requirement", "decision", "work_item", "template_step"]

class Ref(BaseModel):
    type: ObjType
    id: str


# ---- Goal ----
GoalStatus = Literal["proposed", "active", "done", "deprecated"]

class Goal(BaseModel):
    gid: str
    statement: str
    success_metrics: List[str] = Field(default_factory=list)
    priority: int = 0
    status: GoalStatus = "active"


# ---- Requirement ----
RequirementType = Literal["functional", "nfr"]
RequirementStatus = Literal["draft", "refined", "approved", "deprecated"]

class Requirement(BaseModel):
    rid: str
    type: RequirementType
    statement: str
    acceptance_criteria: List[str] = Field(default_factory=list)
    source_goal_ids: List[str] = Field(default_factory=list)
    status: RequirementStatus = "draft"

    @model_validator(mode="after")
    def _must_link_to_goal(self) -> "Requirement":
        if not self.source_goal_ids:
            raise ValueError(f"Requirement {self.rid} must link to at least one goal (source_goal_ids)")
        return self


# ---- Uncertainty register ----
UncertaintyKind = Literal["assumption", "open_question", "risk"]
UncertaintyStatus = Literal["open", "triaged", "deferred", "resolved"]
Impact = Literal["low", "medium", "high"]

class UncertaintyItem(BaseModel):
    uid: str
    kind: UncertaintyKind
    text: str

    status: UncertaintyStatus = "open"
    impact: Impact = "medium"

    # If True, this must be resolved before proceeding past some gate.
    blocks_progress: bool = False

    # Optional "must resolve by" gate reference (milestone, template_step, etc.)
    must_resolve_by: Optional[Ref] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_reviewed_at: Optional[datetime] = None

    # Links for drill-down / alternate views
    links: List[Ref] = Field(default_factory=list)


# ---- WorkItem summary at project layer ----
WorkItemStatus = Literal["todo", "in_progress", "done", "blocked"]

class ProjectWorkItem(BaseModel):
    """
    Project-level view of work items (NOT the template-step WorkItem model).
    This stays light and is meant for planning/traceability.

    Your template-based WorkItem remains in starter.model.base; later you can
    unify these (or store an execution pointer) when you wire execution.
    """
    wid: str
    title: str
    status: WorkItemStatus = "todo"
    depends_on: List[str] = Field(default_factory=list)  # wid list
    traces_to: List[Ref] = Field(default_factory=list)   # goal/requirement/decision refs


# ---- Project ----
class Project(BaseModel):
    pid: str
    title: str
    non_goals: List[str] = Field(default_factory=list)

    goals: Dict[str, Goal] = Field(default_factory=dict)
    requirements: Dict[str, Requirement] = Field(default_factory=dict)
    uncertainties: Dict[str, UncertaintyItem] = Field(default_factory=dict)
    work_items: Dict[str, ProjectWorkItem] = Field(default_factory=dict)