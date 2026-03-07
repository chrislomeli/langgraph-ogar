from __future__ import annotations
from typing import Literal
from starter.model.project import Project

Stage = Literal["goals", "requirements", "design", "done"]

# todo - this the hard coded progression
#       -   think we'll need to define the order of stages data driven template style
#       -   or at least more complete
#       - but this is good for starters
def determine_next_stage(project: Project) -> Stage:
    # Conservative and grounded: only unlock requirements once goals exist
    if not project.goals:
        return "goals"
    if not project.requirements:
        return "requirements"
    # Add design later once you model design artifacts/decisions
    return "done"