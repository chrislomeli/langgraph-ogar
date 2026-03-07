"""
Milestone 12: Prompt Templates + LLM Swap.

Tests verify:
  1. PromptTemplate builds structured messages
  2. DeterministicStrategy wraps existing engine
  3. LLMStrategy builds prompts and falls back to deterministic
  4. FallbackStrategy tries primary, falls back on error
  5. Creation subgraph records strategy_used in state
  6. Refinement subgraph works with strategy
  7. Full graph works with each strategy type
  8. Strategy swap is a single parameter change

KEY CONCEPTS:
  - PlannerStrategy ABC: pluggable planning backend
  - DeterministicStrategy: rule-based (what we've always used)
  - LLMStrategy: stub that builds prompts but falls back
  - FallbackStrategy: primary + secondary with automatic fallback
  - PromptTemplate: structured system + user messages for LLM
"""

from __future__ import annotations

import pytest


# -- Test 1: Prompt Templates -------------------------------------

class TestPromptTemplates:
    """Prompt templates should produce structured messages."""

    def test_plan_user_prompt(self):
        from intent.sketch_models import Sketch
        from graph.m12.prompt_templates import build_plan_user_prompt

        sketch = Sketch(prompt="Rock tune in A minor")
        template = build_plan_user_prompt(sketch)

        assert len(template.messages) == 2
        assert template.messages[0].role == "system"
        assert template.messages[1].role == "user"
        assert "Rock tune in A minor" in template.messages[1].content

    def test_refine_user_prompt(self):
        from intent.sketch_models import Sketch
        from intent.planner import DeterministicPlanner
        from graph.m12.prompt_templates import build_refine_user_prompt

        sketch = Sketch(prompt="Rock tune in A minor")
        plan = DeterministicPlanner().plan(sketch)

        template = build_refine_user_prompt(plan, "Add a bridge")
        assert len(template.messages) == 2
        assert "Add a bridge" in template.messages[1].content
        assert plan.title in template.messages[1].content

    def test_to_dicts(self):
        from intent.sketch_models import Sketch
        from graph.m12.prompt_templates import build_plan_user_prompt

        sketch = Sketch(prompt="Jazz ballad")
        template = build_plan_user_prompt(sketch)
        dicts = template.to_dicts()

        assert isinstance(dicts, list)
        assert all(isinstance(d, dict) for d in dicts)
        assert dicts[0]["role"] == "system"
        assert dicts[1]["role"] == "user"


# -- Test 2: DeterministicStrategy --------------------------------

class TestDeterministicStrategy:
    """DeterministicStrategy should wrap the existing engine."""

    def test_plan(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import DeterministicStrategy

        strategy = DeterministicStrategy()
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)

        assert plan is not None
        assert hasattr(plan, "title")
        assert hasattr(plan, "voice_plan")

    def test_refine(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import DeterministicStrategy

        strategy = DeterministicStrategy()
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)

        old_sections = len(plan.form_plan.sections)
        refined = strategy.refine(plan, "Add a bridge")
        new_sections = len(refined.form_plan.sections)

        assert new_sections > old_sections

    def test_name(self):
        from graph.m12.planner_strategy import DeterministicStrategy

        strategy = DeterministicStrategy()
        assert strategy.name == "deterministic"


# -- Test 3: LLMStrategy (stub) -----------------------------------

class TestLLMStrategy:
    """LLMStrategy should build prompts and fall back to deterministic."""

    def test_plan_falls_back(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import LLMStrategy

        strategy = LLMStrategy(model_name="gpt-4")
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)

        # Should produce a valid plan (via fallback)
        assert plan is not None
        assert hasattr(plan, "title")

    def test_refine_falls_back(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import LLMStrategy

        strategy = LLMStrategy()
        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)
        refined = strategy.refine(plan, "Add a bridge")

        assert refined is not None
        assert len(refined.form_plan.sections) > len(plan.form_plan.sections)

    def test_name_includes_model(self):
        from graph.m12.planner_strategy import LLMStrategy

        strategy = LLMStrategy(model_name="gpt-4o")
        assert "gpt-4o" in strategy.name


# -- Test 4: FallbackStrategy -------------------------------------

class TestFallbackStrategy:
    """FallbackStrategy should try primary and fall back on error."""

    def test_uses_primary_when_successful(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import DeterministicStrategy, FallbackStrategy

        primary = DeterministicStrategy()
        secondary = DeterministicStrategy()
        strategy = FallbackStrategy(primary, secondary)

        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)

        assert plan is not None
        assert strategy.last_used == "deterministic"

    def test_falls_back_on_error(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import PlannerStrategy, DeterministicStrategy, FallbackStrategy

        class BrokenStrategy(PlannerStrategy):
            @property
            def name(self):
                return "broken"
            def plan(self, sketch):
                raise RuntimeError("LLM unavailable")
            def refine(self, plan, prompt):
                raise RuntimeError("LLM unavailable")

        primary = BrokenStrategy()
        secondary = DeterministicStrategy()
        strategy = FallbackStrategy(primary, secondary)

        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)

        assert plan is not None
        assert strategy.last_used == "deterministic"

    def test_refine_falls_back_on_error(self):
        from intent.sketch_models import Sketch
        from graph.m12.planner_strategy import PlannerStrategy, DeterministicStrategy, FallbackStrategy

        class BrokenRefineStrategy(PlannerStrategy):
            @property
            def name(self):
                return "broken_refine"
            def plan(self, sketch):
                return DeterministicStrategy().plan(sketch)
            def refine(self, plan, prompt):
                raise RuntimeError("LLM unavailable for refine")

        primary = BrokenRefineStrategy()
        secondary = DeterministicStrategy()
        strategy = FallbackStrategy(primary, secondary)

        sketch = Sketch(prompt="Rock tune in A minor")
        plan = strategy.plan(sketch)  # succeeds via primary
        assert strategy.last_used == "broken_refine"

        refined = strategy.refine(plan, "Add a bridge")  # falls back
        assert refined is not None
        assert strategy.last_used == "deterministic"

    def test_name_shows_chain(self):
        from graph.m12.planner_strategy import DeterministicStrategy, LLMStrategy, FallbackStrategy

        strategy = FallbackStrategy(LLMStrategy("gpt-4"), DeterministicStrategy())
        assert "gpt-4" in strategy.name
        assert "deterministic" in strategy.name


# -- Test 5: Creation subgraph with strategy -----------------------

class TestCreationSubgraphWithStrategy:
    """Creation subgraph should record strategy_used in state."""

    def test_deterministic_strategy_recorded(self):
        from graph.m12.planner_strategy import DeterministicStrategy
        from graph.m12.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph(strategy=DeterministicStrategy())
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert result.get("strategy_used") == "deterministic"
        assert "Strategy: deterministic" in result["response"]

    def test_llm_strategy_recorded(self):
        from graph.m12.planner_strategy import LLMStrategy
        from graph.m12.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph(strategy=LLMStrategy("gpt-4"))
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "gpt-4" in result.get("strategy_used", "")
        assert "Created" in result["response"]

    def test_creation_produces_correct_output(self):
        from graph.m12.subgraphs.creation import build_creation_subgraph

        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "plan" in result
        assert "compile_result" in result
        assert "response" in result
        assert hasattr(result["plan"], "title")


# -- Test 6: Refinement subgraph with strategy ---------------------

class TestRefinementSubgraphWithStrategy:
    """Refinement should work with strategy."""

    def _get_previous_artifacts(self):
        from graph.m12.subgraphs.creation import build_creation_subgraph
        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})
        return result["plan"], result["compile_result"]

    def test_refinement_with_deterministic(self):
        from graph.m12.planner_strategy import DeterministicStrategy
        from graph.m12.subgraphs.refinement import build_refinement_subgraph

        plan, compile_result = self._get_previous_artifacts()
        app = build_refinement_subgraph(strategy=DeterministicStrategy())

        old_sections = len(plan.form_plan.sections)
        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert len(result["plan"].form_plan.sections) > old_sections
        assert result.get("strategy_used") == "deterministic"


# -- Test 7: Full graph with strategy swap -------------------------

class TestFullGraphWithStrategy:
    """Full graph should work with different strategies."""

    def test_default_deterministic(self):
        from graph.m12.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "m12-1"}}
        result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        assert "Created" in result["response"]
        assert "deterministic" in result.get("strategy_used", "")

    def test_llm_strategy_swap(self):
        from graph.m12.graph_builder import build_music_graph
        from graph.m12.planner_strategy import LLMStrategy

        app = build_music_graph(strategy=LLMStrategy("gpt-4"))
        config = {"configurable": {"thread_id": "m12-2"}}
        result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        assert "Created" in result["response"]
        assert "gpt-4" in result.get("strategy_used", "")

    def test_fallback_strategy_swap(self):
        from graph.m12.graph_builder import build_music_graph
        from graph.m12.planner_strategy import DeterministicStrategy, LLMStrategy, FallbackStrategy

        strategy = FallbackStrategy(LLMStrategy("gpt-4"), DeterministicStrategy())
        app = build_music_graph(strategy=strategy)
        config = {"configurable": {"thread_id": "m12-3"}}
        result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        assert "Created" in result["response"]

    def test_create_refine_save_load(self):
        from graph.m12.store import InMemoryStore
        from graph.m12.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m12-4"}}

        # Create
        app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        # Refine
        refine_result = app.invoke({"user_message": "Add a bridge"}, config)
        refined_plan = refine_result["plan"]

        # Save
        app.invoke({"user_message": "Save as My M12 Tune"}, config)
        assert store.exists("My M12 Tune")

        # Load in new session
        config2 = {"configurable": {"thread_id": "m12-5"}}
        load_result = app.invoke({"user_message": "Load My M12 Tune"}, config2)
        assert load_result["plan"].form_plan.total_bars() == refined_plan.form_plan.total_bars()

    def test_list_projects(self):
        from graph.m12.store import InMemoryStore
        from graph.m12.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m12-6"}}

        result = app.invoke({"user_message": "List my projects"}, config)
        assert "No saved projects" in result["response"]
