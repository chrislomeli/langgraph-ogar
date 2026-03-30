"""
Planner Strategy -- M12: Pluggable planning backends.

KEY CONCEPT: The PlannerStrategy ABC defines the contract for how a
Sketch becomes a PlanBundle. Two implementations:

  1. DeterministicStrategy: wraps the existing DeterministicPlanner.
     This is what we've been using all along -- rule-based, no LLM.

  2. LLMStrategy (stub): placeholder for a real LLM call. It builds
     a structured prompt via PromptTemplate, then falls back to
     deterministic because there's no actual LLM wired up.

  3. FallbackStrategy: tries the primary strategy (e.g. LLM), catches
     errors, and falls back to a secondary strategy (e.g. deterministic).
     This is the production pattern: LLM for quality, deterministic for
     reliability.

The strategy is injected into the domain executors, replacing the
hard-coded DeterministicPlanner calls.
"""

from __future__ import annotations

import abc
import logging
from typing import Any

from intent.sketch_models import Sketch
from intent.planner import DeterministicPlanner
from intent.compiler import PatternCompiler

from .prompt_templates import build_plan_user_prompt, build_refine_user_prompt

logger = logging.getLogger(__name__)


class PlannerStrategy(abc.ABC):
    """ABC for planning backends."""

    @abc.abstractmethod
    def plan(self, sketch: Sketch) -> Any:
        """Generate a PlanBundle from a Sketch."""
        ...

    @abc.abstractmethod
    def refine(self, plan: Any, prompt: str) -> Any:
        """Refine an existing PlanBundle."""
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Human-readable name of this strategy."""
        ...


class DeterministicStrategy(PlannerStrategy):
    """Wraps the existing DeterministicPlanner. No LLM calls."""

    def __init__(self):
        self._planner = DeterministicPlanner()

    @property
    def name(self) -> str:
        return "deterministic"

    def plan(self, sketch: Sketch) -> Any:
        return self._planner.plan(sketch)

    def refine(self, plan: Any, prompt: str) -> Any:
        return self._planner.refine(plan, prompt)


class LLMStrategy(PlannerStrategy):
    """
    Stub LLM strategy -- builds structured prompts but falls back
    to deterministic planning.

    In a real implementation, this would:
      1. Build a PromptTemplate
      2. Send it to an LLM (e.g. ChatOpenAI)
      3. Parse the structured JSON response into a PlanBundle
      4. Validate with Pydantic

    For now it demonstrates the prompt construction and falls back
    to deterministic so tests pass without an API key.
    """

    def __init__(self, model_name: str = "gpt-4"):
        self._model_name = model_name
        self._fallback = DeterministicPlanner()

    @property
    def name(self) -> str:
        return f"llm:{self._model_name}"

    def plan(self, sketch: Sketch) -> Any:
        # Build the prompt (this is what would go to the LLM)
        prompt_template = build_plan_user_prompt(sketch)
        messages = prompt_template.to_dicts()

        logger.info(
            "[LLMStrategy] Would send %d messages to %s (falling back to deterministic)",
            len(messages), self._model_name,
        )

        # Stub: fall back to deterministic
        return self._fallback.plan(sketch)

    def refine(self, plan: Any, prompt: str) -> Any:
        prompt_template = build_refine_user_prompt(plan, prompt)
        messages = prompt_template.to_dicts()

        logger.info(
            "[LLMStrategy] Would send %d refinement messages to %s (falling back to deterministic)",
            len(messages), self._model_name,
        )

        return self._fallback.refine(plan, prompt)


class FallbackStrategy(PlannerStrategy):
    """
    Tries a primary strategy, falls back to secondary on error.

    This is the production pattern:
      - Primary: LLMStrategy (quality, creative)
      - Secondary: DeterministicStrategy (reliable, predictable)

    If the primary raises any exception, the secondary is used
    and the fallback is logged.
    """

    def __init__(self, primary: PlannerStrategy, secondary: PlannerStrategy):
        self._primary = primary
        self._secondary = secondary
        self._last_used: str = ""

    @property
    def name(self) -> str:
        return f"fallback({self._primary.name} -> {self._secondary.name})"

    @property
    def last_used(self) -> str:
        """Which strategy was actually used on the last call."""
        return self._last_used

    def plan(self, sketch: Sketch) -> Any:
        try:
            result = self._primary.plan(sketch)
            self._last_used = self._primary.name
            return result
        except Exception as e:
            logger.warning(
                "[FallbackStrategy] Primary (%s) failed: %s. Using secondary (%s).",
                self._primary.name, e, self._secondary.name,
            )
            result = self._secondary.plan(sketch)
            self._last_used = self._secondary.name
            return result

    def refine(self, plan: Any, prompt: str) -> Any:
        try:
            result = self._primary.refine(plan, prompt)
            self._last_used = self._primary.name
            return result
        except Exception as e:
            logger.warning(
                "[FallbackStrategy] Primary (%s) failed on refine: %s. Using secondary (%s).",
                self._primary.name, e, self._secondary.name,
            )
            result = self._secondary.refine(plan, prompt)
            self._last_used = self._secondary.name
            return result
