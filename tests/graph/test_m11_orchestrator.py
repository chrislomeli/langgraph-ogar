"""
Milestone 11: PlanOrchestrator Integration.

Tests verify:
  1. ScopeRegistry has all domain executors registered
  2. PlanGraph DAG is correctly constructed
  3. PlanOrchestrator drives creation pipeline to completion
  4. Orchestrator events are emitted during execution
  5. Creation subgraph produces correct results via orchestrator
  6. Refinement subgraph works via orchestrator
  7. Full parent graph works end-to-end
  8. Create -> refine -> save -> load multi-turn workflow

KEY CONCEPTS:
  - PlanGraph: DAG of SubPlans (sketch_parse -> plan_composition -> compile_composition)
  - ScopeRegistry: maps scope_type to domain planners + executors
  - PlanOrchestrator: drives DAG lifecycle (draft -> approved -> executing -> done)
  - AlwaysApprove: auto-approve policy for fully autonomous execution
"""

from __future__ import annotations

import pytest


# -- Test 1: ScopeRegistry ----------------------------------------

class TestScopeRegistry:
    """ScopeRegistry should have all domain executors."""

    def test_registry_has_all_scope_types(self):
        from graph.m11.domain_executors import build_scope_registry

        registry = build_scope_registry()
        types = registry.registered_types()
        assert "sketch_parse" in types
        assert "plan_composition" in types
        assert "compile_composition" in types

    def test_registry_returns_planners_and_executors(self):
        from graph.m11.domain_executors import build_scope_registry

        registry = build_scope_registry()
        for scope_type in ["sketch_parse", "plan_composition", "compile_composition"]:
            planner = registry.get_planner(scope_type)
            executor = registry.get_executor(scope_type)
            assert planner is not None
            assert executor is not None


# -- Test 2: PlanGraph DAG ----------------------------------------

class TestPlanGraphDAG:
    """PlanGraph should represent the creation pipeline as a DAG."""

    def test_creation_dag_structure(self):
        from graph.m11.domain_executors import build_creation_plan_graph

        graph = build_creation_plan_graph("Rock tune in A minor")

        assert "sketch_parse" in graph.sub_plans
        assert "plan_composition" in graph.sub_plans
        assert "compile_composition" in graph.sub_plans

        # Check dependencies
        assert graph.dependencies["sketch_parse"] == set()
        assert graph.dependencies["plan_composition"] == {"sketch_parse"}
        assert graph.dependencies["compile_composition"] == {"plan_composition"}

    def test_sketch_parse_has_user_message(self):
        from graph.m11.domain_executors import build_creation_plan_graph

        graph = build_creation_plan_graph("Rock tune in A minor")
        sketch_sp = graph.get("sketch_parse")
        assert sketch_sp.content == "Rock tune in A minor"

    def test_all_start_as_draft(self):
        from graph.m11.domain_executors import build_creation_plan_graph
        from framework.langgraph_ext.planning.models import SubPlanStatus

        graph = build_creation_plan_graph("Rock tune")
        for sp in graph.sub_plans.values():
            assert sp.status == SubPlanStatus.draft


# -- Test 3: PlanOrchestrator drives creation ----------------------

class TestOrchestratorCreation:
    """PlanOrchestrator should drive the creation pipeline to completion."""

    def test_orchestrator_completes_all_steps(self):
        from graph.m11.domain_executors import build_scope_registry, build_creation_plan_graph
        from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator
        from framework.langgraph_ext.planning.approval import AlwaysApprove
        from framework.langgraph_ext.planning.models import SubPlanStatus

        registry = build_scope_registry()
        plan_graph = build_creation_plan_graph("Rock tune in A minor")

        orchestrator = PlanOrchestrator(
            registry=registry,
            approval_policy=AlwaysApprove(),
        )
        orchestrator.load_plan(plan_graph)
        result = orchestrator.run()

        assert result.complete
        for sp in plan_graph.sub_plans.values():
            assert sp.status == SubPlanStatus.done

    def test_orchestrator_produces_sketch(self):
        from graph.m11.domain_executors import build_scope_registry, build_creation_plan_graph
        from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator
        from framework.langgraph_ext.planning.approval import AlwaysApprove

        registry = build_scope_registry()
        plan_graph = build_creation_plan_graph("Rock tune in A minor")

        orchestrator = PlanOrchestrator(registry=registry, approval_policy=AlwaysApprove())
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        sketch = plan_graph.get("sketch_parse").result
        assert sketch is not None
        assert hasattr(sketch, "prompt")

    def test_orchestrator_produces_plan_bundle(self):
        from graph.m11.domain_executors import build_scope_registry, build_creation_plan_graph
        from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator
        from framework.langgraph_ext.planning.approval import AlwaysApprove

        registry = build_scope_registry()
        plan_graph = build_creation_plan_graph("Rock tune in A minor")

        orchestrator = PlanOrchestrator(registry=registry, approval_policy=AlwaysApprove())
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        plan = plan_graph.get("plan_composition").result
        assert plan is not None
        assert hasattr(plan, "title")
        assert hasattr(plan, "voice_plan")

    def test_orchestrator_produces_compile_result(self):
        from graph.m11.domain_executors import build_scope_registry, build_creation_plan_graph
        from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator
        from framework.langgraph_ext.planning.approval import AlwaysApprove

        registry = build_scope_registry()
        plan_graph = build_creation_plan_graph("Rock tune in A minor")

        orchestrator = PlanOrchestrator(registry=registry, approval_policy=AlwaysApprove())
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        result = plan_graph.get("compile_composition").result
        assert result is not None
        assert hasattr(result, "composition")

    def test_orchestrator_emits_events(self):
        from graph.m11.domain_executors import build_scope_registry, build_creation_plan_graph
        from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator, OrchestratorEvent
        from framework.langgraph_ext.planning.approval import AlwaysApprove

        events = []
        registry = build_scope_registry()
        plan_graph = build_creation_plan_graph("Rock tune in A minor")

        orchestrator = PlanOrchestrator(
            registry=registry,
            approval_policy=AlwaysApprove(),
            on_event=lambda e: events.append(e),
        )
        orchestrator.load_plan(plan_graph)
        orchestrator.run()

        event_kinds = [e.kind.value for e in events]
        assert "plan_proposed" in event_kinds
        assert "sub_plan_done" in event_kinds
        assert "plan_complete" in event_kinds


# -- Test 4: Creation subgraph via orchestrator --------------------

class TestCreationSubgraphOrchestrated:
    """Creation subgraph should produce correct results via orchestrator."""

    def _build_creation_app(self):
        from graph.m11.subgraphs.creation import build_creation_subgraph
        return build_creation_subgraph()

    def test_creation_produces_plan(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "plan" in result
        assert result["plan"] is not None
        assert hasattr(result["plan"], "title")

    def test_creation_produces_compile_result(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "compile_result" in result
        assert hasattr(result["compile_result"], "composition")

    def test_creation_produces_response(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "response" in result
        assert "Created" in result["response"]

    def test_creation_has_plan_graph(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        assert "plan_graph" in result
        assert result["plan_graph"] is not None

    def test_creation_has_orchestrator_events(self):
        app = self._build_creation_app()
        result = app.invoke({"user_message": "Rock tune in A minor"})

        events = result.get("orchestrator_events", [])
        assert len(events) > 0
        kinds = [e["kind"] for e in events]
        assert "plan_proposed" in kinds


# -- Test 5: Refinement subgraph via orchestrator ------------------

class TestRefinementSubgraphOrchestrated:
    """Refinement subgraph should work via orchestrator."""

    def _get_previous_artifacts(self):
        from graph.m11.subgraphs.creation import build_creation_subgraph
        app = build_creation_subgraph()
        result = app.invoke({"user_message": "Rock tune in A minor"})
        return result["plan"], result["compile_result"]

    def _build_refinement_app(self):
        from graph.m11.subgraphs.refinement import build_refinement_subgraph
        return build_refinement_subgraph()

    def test_add_bridge_refinement(self):
        plan, compile_result = self._get_previous_artifacts()
        app = self._build_refinement_app()

        old_sections = len(plan.form_plan.sections)
        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert "plan" in result
        new_sections = len(result["plan"].form_plan.sections)
        assert new_sections > old_sections

    def test_refinement_produces_response(self):
        plan, compile_result = self._get_previous_artifacts()
        app = self._build_refinement_app()

        result = app.invoke({
            "user_message": "Add a bridge",
            "previous_plan": plan,
            "previous_compile_result": compile_result,
        })

        assert "response" in result
        assert "Refined" in result["response"]


# -- Test 6: Full parent graph ------------------------------------

class TestFullGraphOrchestrated:
    """The parent graph should work end-to-end with orchestrator."""

    def test_create_composition(self):
        from graph.m11.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "m11-1"}}
        result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)

        assert "response" in result
        assert "Created" in result["response"]

    def test_create_then_refine(self):
        from graph.m11.graph_builder import build_music_graph

        app = build_music_graph()
        config = {"configurable": {"thread_id": "m11-2"}}

        create_result = app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        old_bars = create_result["plan"].form_plan.total_bars()

        refine_result = app.invoke({"user_message": "Add a bridge"}, config)
        new_bars = refine_result["plan"].form_plan.total_bars()

        assert new_bars > old_bars

    def test_create_save_load(self):
        from graph.m11.store import InMemoryStore
        from graph.m11.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m11-3"}}

        app.invoke({"user_message": "Write a rock tune in A minor"}, config)
        app.invoke({"user_message": "Save as My M11 Tune"}, config)
        assert store.exists("My M11 Tune")

        config2 = {"configurable": {"thread_id": "m11-4"}}
        load_result = app.invoke({"user_message": "Load My M11 Tune"}, config2)
        assert load_result["plan"] is not None

    def test_list_projects(self):
        from graph.m11.store import InMemoryStore
        from graph.m11.graph_builder import build_music_graph

        store = InMemoryStore()
        app = build_music_graph(store=store)
        config = {"configurable": {"thread_id": "m11-5"}}

        result = app.invoke({"user_message": "List my projects"}, config)
        assert "No saved projects" in result["response"]
