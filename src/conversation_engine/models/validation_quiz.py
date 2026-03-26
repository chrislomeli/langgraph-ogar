"""
Validation quiz model — a pure data definition for LLM pre-run validation.

This lives in the models layer because it is a domain data structure with
zero infrastructure dependencies.  The infrastructure layer
(``infrastructure.llm.validator``) *consumes* it at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ValidationQuiz:
    """
    A single quiz question for LLM pre-run validation.

    Attributes:
        question: The question to ask the LLM.
        required_concepts: Keywords/phrases that MUST appear in the response
                          (case-insensitive). Each found concept scores equally.
        prohibited_concepts: Keywords/phrases that must NOT appear (hallucination
                            detection). Each found concept penalizes the score.
        weight: Relative weight of this question in the overall score.
        min_score: Minimum fraction of required_concepts that must be present
                  for this question to pass (0.0–1.0). Default 0.5.
    """
    question: str
    required_concepts: List[str]
    prohibited_concepts: List[str] = field(default_factory=list)
    weight: float = 1.0
    min_score: float = 0.5
