"""Tests for intent.plan_adapter — music domain ↔ plan framework bridge."""

from __future__ import annotations

import pytest

from framework.langgraph_ext.planning.models import SubPlanStatus
from framework.langgraph_ext.planning.orchestrator import PlanOrchestrator

from intent.plan_adapter import (
    ALL_SCOPES,
    MUSIC_DEPENDENCIES,
    SCOPE_COMPILATION,
    SCOPE_FORM,
    SCOPE_GROOVE,
    SCOPE_HARMONY,
    SCOPE_VOICES,
    bundle_to_plan_graph,
    music_registry,
    plan_graph_to_bundle,
)
from intent.plan_models import (
    ChordEvent,
    ChordQuality,
    DensityLevel,
    EnergyLevel,
    FormPlan,
    GrooveFeel,
    GroovePlan,
    GrooveSectionPlan,
    HarmonyPlan,
    HarmonySectionPlan,
    PlanBundle,
    RenderPlan,
    SectionPlan,
    SectionRole,
    TimelinePlacement,
    VoicePlan,
    VoiceRole,
    VoiceSpec,
)


# ── Fixtures ────────────────────────────────────────────────────────


def _minimal_bundle() -> PlanBundle:
    """A minimal valid PlanBundle for testing."""
    return PlanBundle(
        title="Test Song",
        key="C major",
        tempo_bpm=120,
        time_signature="4/4",
        voice_plan=VoicePlan(
            voices=(
                VoiceSpec(
                    voice_id="drums",
                    name="Drums",
                    role=VoiceRole.drums,
                    instrument="drum_kit",
                ),
                VoiceSpec(
                    voice_id="bass",
                    name="Bass",
                    role=VoiceRole.bass,
                    instrument="electric_bass",
                ),
            ),
        ),
        form_plan=FormPlan(
            sections=(
                SectionPlan(
                    section_id="verse",
                    role=SectionRole.verse,
                    bars=8,
                    energy=EnergyLevel.medium,
                ),
                SectionPlan(
                    section_id="chorus",
                    role=SectionRole.chorus,
                    bars=8,
                    energy=EnergyLevel.high,
                ),
            ),
            timeline=(
                TimelinePlacement(section_id="verse", start_bar=1),
                TimelinePlacement(section_id="chorus", start_bar=9),
            ),
        ),
        harmony_plan=HarmonyPlan(
            sections=(
                HarmonySectionPlan(
                    section_id="verse",
                    key="C major",
                    chords=(
                        ChordEvent(at_bar=1, root="C", quality=ChordQuality.maj),
                        ChordEvent(at_bar=5, root="G", quality=ChordQuality.maj),
                    ),
                ),
                HarmonySectionPlan(
                    section_id="chorus",
                    key="C major",
                    chords=(
                        ChordEvent(at_bar=1, root="F", quality=ChordQuality.maj),
                        ChordEvent(at_bar=5, root="G", quality=ChordQuality.maj),
                    ),
                ),
            ),
        ),
        groove_plan=GroovePlan(
            global_feel=GrooveFeel.straight,
            sections=(
                GrooveSectionPlan(section_id="verse", feel=GrooveFeel.straight),
                GrooveSectionPlan(section_id="chorus", feel=GrooveFeel.straight),
            ),
        ),
        render_plan=RenderPlan(),
    )


# ── bundle_to_plan_graph ────────────────────────────────────────────


class TestBundleToPlanGraph:
    def test_creates_all_scopes(self):
        graph = bundle_to_plan_graph(_minimal_bundle())
        assert set(graph.sub_plans.keys()) == set(ALL_SCOPES)

    def test_dependencies_match(self):
        graph = bundle_to_plan_graph(_minimal_bundle())
        assert graph.dependencies == MUSIC_DEPENDENCIES

    def test_voice_content_is_dict(self):
        graph = bundle_to_plan_graph(_minimal_bundle())
        content = graph.sub_plans[SCOPE_VOICES].content
        assert isinstance(content, dict)
        assert "voices" in content

    def test_compilation_has_no_content(self):
        graph = bundle_to_plan_graph(_minimal_bundle())
        assert graph.sub_plans[SCOPE_COMPILATION].content is None

    def test_scope_types_set_correctly(self):
        graph = bundle_to_plan_graph(_minimal_bundle())
        for scope_id in ALL_SCOPES:
            assert graph.sub_plans[scope_id].scope_type == scope_id


# ── plan_graph_to_bundle ────────────────────────────────────────────


class TestPlanGraphToBundle:
    def test_round_trip_preserves_voices(self):
        original = _minimal_bundle()
        graph = bundle_to_plan_graph(original)
        restored = plan_graph_to_bundle(graph, original)
        assert len(restored.voice_plan.voices) == len(original.voice_plan.voices)
        assert restored.voice_plan.voices[0].voice_id == "drums"

    def test_round_trip_preserves_form(self):
        original = _minimal_bundle()
        graph = bundle_to_plan_graph(original)
        restored = plan_graph_to_bundle(graph, original)
        assert len(restored.form_plan.sections) == len(original.form_plan.sections)

    def test_round_trip_preserves_global_fields(self):
        original = _minimal_bundle()
        graph = bundle_to_plan_graph(original)
        restored = plan_graph_to_bundle(graph, original)
        assert restored.title == original.title
        assert restored.key == original.key
        assert restored.tempo_bpm == original.tempo_bpm


# ── music_registry ──────────────────────────────────────────────────


class TestMusicRegistry:
    def test_all_scopes_registered(self):
        reg = music_registry()
        for scope in ALL_SCOPES:
            assert reg.has(scope)

    def test_registered_types(self):
        reg = music_registry()
        assert set(reg.registered_types()) == set(ALL_SCOPES)


# ── Orchestrator integration ────────────────────────────────────────


class TestOrchestratorIntegration:
    def test_run_to_completion(self):
        """Full pipeline: PlanBundle → PlanGraph → orchestrate → done."""
        bundle = _minimal_bundle()
        graph = bundle_to_plan_graph(bundle)
        reg = music_registry()  # no compiler = dry run

        orch = PlanOrchestrator(registry=reg)
        orch.load_plan(graph)
        result = orch.run()

        assert result.complete
        assert orch.is_complete

        # All sub-plans should be done
        for scope_id in ALL_SCOPES:
            assert graph.sub_plans[scope_id].status == SubPlanStatus.done

    def test_execution_order_respects_deps(self):
        """Verify that voices runs before form, form before harmony/groove, etc."""
        bundle = _minimal_bundle()
        graph = bundle_to_plan_graph(bundle)
        reg = music_registry()

        execution_order = []

        def track_event(event):
            if event.kind.value == "sub_plan_done" and event.scope_id:
                execution_order.append(event.scope_id)

        orch = PlanOrchestrator(registry=reg, on_event=track_event)
        orch.load_plan(graph)
        orch.run()

        # voices must come before form
        assert execution_order.index(SCOPE_VOICES) < execution_order.index(SCOPE_FORM)
        # form must come before harmony and groove
        assert execution_order.index(SCOPE_FORM) < execution_order.index(SCOPE_HARMONY)
        assert execution_order.index(SCOPE_FORM) < execution_order.index(SCOPE_GROOVE)
        # harmony and groove must come before compilation
        assert execution_order.index(SCOPE_HARMONY) < execution_order.index(SCOPE_COMPILATION)
        assert execution_order.index(SCOPE_GROOVE) < execution_order.index(SCOPE_COMPILATION)

    def test_executor_results_contain_validation(self):
        """Executors validate Pydantic models and report results."""
        bundle = _minimal_bundle()
        graph = bundle_to_plan_graph(bundle)
        reg = music_registry()

        orch = PlanOrchestrator(registry=reg)
        orch.load_plan(graph)
        orch.run()

        assert "2 voices" in graph.sub_plans[SCOPE_VOICES].result
        assert "2 sections" in graph.sub_plans[SCOPE_FORM].result
        assert "2 sections" in graph.sub_plans[SCOPE_HARMONY].result
        assert "2 sections" in graph.sub_plans[SCOPE_GROOVE].result
        assert "dry run" in graph.sub_plans[SCOPE_COMPILATION].result
