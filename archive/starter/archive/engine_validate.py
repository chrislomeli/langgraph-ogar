from typing import Set, Dict, Optional

from starter.model.base import WorkItem, Template


def can_mark_done(template: Template, item: WorkItem, step_id: str) -> None:
    step_def = next(s for s in template.steps if s.step_id == step_id)
    inst = item.steps[step_id]
    missing = [f for f in step_def.required_fields if f not in inst.payload]
    if missing:
        raise ValueError(f"Cannot complete '{step_id}': missing required fields: {missing}")

