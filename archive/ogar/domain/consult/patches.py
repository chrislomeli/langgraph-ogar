from __future__ import annotations
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from ogar.domain.models.project import Goal, Requirement, UncertaintyItem

class ProjectPatch(BaseModel):
    """
    LLM outputs THIS, then code applies it.
    """
    # Optional title update
    title: Optional[str] = None

    # Adds or replaces these objects by ID
    goals_upsert: Dict[str, Goal] = Field(default_factory=dict)
    requirements_upsert: Dict[str, Requirement] = Field(default_factory=dict)
    uncertainties_upsert: Dict[str, UncertaintyItem] = Field(default_factory=dict)

    # Optional: questions for user (LLM may propose, but code decides blockers)
    suggested_questions: List[str] = Field(default_factory=list)