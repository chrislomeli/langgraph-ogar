from __future__ import annotations


from typing import Dict, List, Optional, Literal, Set
from pydantic import BaseModel, Field, model_validator


StepKind = Literal["artifact", "decision", "check", "hitl_gate"]
StepStatus = Literal["todo", "in_progress", "done", "blocked"]

class TemplateStep(BaseModel):
    step_id: str = Field(..., min_length=1)
    kind: StepKind
    title: str
    # purely a view/label (optional): "requirements", "design", etc.
    phase: Optional[str] = None

    # enforce requirements by declaring what payload fields must exist
    required_fields: List[str] = Field(default_factory=list)

    # optional: you can use this to compute progress weighting later
    weight: int = 1


class TemplateEdge(BaseModel):
    # "to" depends on "frm"
    frm: str
    to: str


class Template(BaseModel):
    template_id: str
    name: str
    steps: List[TemplateStep]
    edges: List[TemplateEdge] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_template(self) -> "Template":
        step_ids = {s.step_id for s in self.steps}
        if len(step_ids) != len(self.steps):
            raise ValueError("Duplicate step_id in template.steps")

        for e in self.edges:
            if e.frm not in step_ids or e.to not in step_ids:
                raise ValueError(f"Edge refers to unknown step_id: {e}")

        # basic cycle check (Kahn)
        incoming: Dict[str, int] = {sid: 0 for sid in step_ids}
        outgoing: Dict[str, List[str]] = {sid: [] for sid in step_ids}
        for e in self.edges:
            incoming[e.to] += 1
            outgoing[e.frm].append(e.to)

        queue = [sid for sid, deg in incoming.items() if deg == 0]
        seen = 0
        while queue:
            n = queue.pop()
            seen += 1
            for m in outgoing[n]:
                incoming[m] -= 1
                if incoming[m] == 0:
                    queue.append(m)

        if seen != len(step_ids):
            raise ValueError("Template edges contain a cycle (DAG required)")

        return self



class StepInstance(BaseModel):
    status: StepStatus = "todo"
    payload: Dict[str, object] = Field(default_factory=dict)


class WorkItem(BaseModel):
    work_id: str
    title: str
    template_id: str

    # Instances keyed by step_id
    steps: Dict[str, StepInstance] = Field(default_factory=dict)

    # Collaboration artifacts (optional, but strongly recommended)
    open_ambiguities: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    decisions: List[Dict[str, object]] = Field(default_factory=list)

    @classmethod
    def instantiate_from_template(
        cls,
        work_id: str,
        title: str,
        template: Template,
    ) -> "WorkItem":
        return cls(
            work_id=work_id,
            title=title,
            template_id=template.template_id,
            steps={s.step_id: StepInstance() for s in template.steps},
        )