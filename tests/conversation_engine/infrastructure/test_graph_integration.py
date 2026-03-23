"""
Integration tests: infrastructure wired into the conversation graph.

Covers:
- New NodeMiddleware system with build_conversation_graph
- Legacy interceptors still work (backwards compatibility)
- Middleware composition in real conversation runs
- ErrorHandlingMiddleware replaces handle_error node
- LLM injectable via state["llm"] (stub)
- Pre-flight LLM validation: smart LLM passes, dumb LLM raises
"""
import pytest

from conversation_engine.graph.context import (
    ConversationContext,
    Finding,
    ValidationResult,
)
from conversation_engine.graph.builder import (
    build_conversation_graph,
    LLMPreflightError,
    MAX_TURNS,
)
from conversation_engine.infrastructure.interceptors import (
    MetricsInterceptor,
    LoggingInterceptor,
)
from conversation_engine.infrastructure.middleware import (
    LoggingMiddleware,
    MetricsMiddleware,
    ErrorHandlingMiddleware,
)
from conversation_engine.infrastructure.llm import (
    CallLLM,
    LLMRequest,
    LLMResponse,
    ValidationQuiz,
    call_llm_stub,
)


# ── Fake contexts ───────────────────────────────────────────────────

class _CleanContext:
    """Context with no findings — graph exits in one pass."""

    def validate(self, prior_findings):
        return ValidationResult(findings=[])

    def format_finding_summary(self, findings):
        return "All clear."

    def get_domain_state(self):
        return {}

    @property
    def system_prompt(self) -> str:
        return "You are a test assistant."

    @property
    def preflight_quiz(self) -> list:
        return []


class _GappyContext:
    """Context that always returns one finding — graph loops to max turns."""

    def validate(self, prior_findings):
        resolved = [f for f in prior_findings if f.resolved]
        return ValidationResult(findings=resolved + [
            Finding(
                id="gap-1",
                finding_type="test_gap",
                severity="high",
                subject_ids=["x"],
                message="Something is missing.",
            ),
        ])

    def format_finding_summary(self, findings):
        return f"{len(findings)} issue(s) found."

    def get_domain_state(self):
        return {}

    @property
    def system_prompt(self) -> str:
        return "You are a test assistant."

    @property
    def preflight_quiz(self) -> list:
        return []


class _FailingContext:
    """Context whose validate() raises — tests error routing."""

    def validate(self, prior_findings):
        raise RuntimeError("context exploded")

    def format_finding_summary(self, findings):
        return ""

    def get_domain_state(self):
        return {}

    @property
    def system_prompt(self) -> str:
        return ""

    @property
    def preflight_quiz(self) -> list:
        return []


def _make_state(ctx, llm=None):
    return {
        "context": ctx,
        "session_id": "infra-test",
        "llm": llm,
        "findings": [],
        "messages": [],
        "current_turn": 0,
        "status": "running",
        "node_result": None,
    }


# ── Tests ───────────────────────────────────────────────────────────

class TestInterceptorsInGraph:

    def test_metrics_collected_on_clean_run(self):
        """MetricsInterceptor collects data for all nodes during a clean run."""
        mi = MetricsInterceptor()
        graph = build_conversation_graph(interceptors=[mi])
        state = _make_state(_CleanContext())

        result = graph.invoke(state)

        snap = mi.snapshot()
        # All three nodes should have been called at least once
        assert "validate" in snap
        assert "reason" in snap
        assert "respond" in snap
        assert snap["validate"]["call_count"] >= 1
        assert snap["reason"]["call_count"] >= 1
        assert snap["respond"]["call_count"] >= 1

    def test_metrics_on_looping_run(self):
        """MetricsInterceptor shows multiple calls when graph loops."""
        mi = MetricsInterceptor()
        graph = build_conversation_graph(interceptors=[mi])
        state = _make_state(_GappyContext())

        result = graph.invoke(state)

        snap = mi.snapshot()
        assert snap["validate"]["call_count"] == MAX_TURNS
        assert snap["reason"]["call_count"] == MAX_TURNS
        assert snap["respond"]["call_count"] == MAX_TURNS

    def test_logging_interceptor_no_crash(self):
        """LoggingInterceptor runs without crashing the graph."""
        graph = build_conversation_graph(interceptors=[LoggingInterceptor()])
        state = _make_state(_CleanContext())

        result = graph.invoke(state)
        assert result["current_turn"] == 1

    def test_multiple_interceptors(self):
        """Multiple interceptors compose correctly."""
        mi = MetricsInterceptor()
        graph = build_conversation_graph(
            interceptors=[LoggingInterceptor(), mi],
        )
        state = _make_state(_CleanContext())

        result = graph.invoke(state)

        assert "validate" in mi.snapshot()
        assert result["current_turn"] == 1


class TestErrorRoutingInGraph:

    def test_failing_context_propagates_without_error_mw(self):
        """Without ErrorHandlingMiddleware, exceptions propagate."""
        graph = build_conversation_graph()
        state = _make_state(_FailingContext())

        with pytest.raises(RuntimeError, match="context exploded"):
            graph.invoke(state)

    def test_failing_context_caught_by_error_middleware(self):
        """ErrorHandlingMiddleware catches the exception and sets status='error'."""
        mm = MetricsMiddleware()
        ehm = ErrorHandlingMiddleware(swallow_exceptions=True)
        graph = build_conversation_graph(node_middleware=[mm, ehm])
        state = _make_state(_FailingContext())

        result = graph.invoke(state)

        assert result["status"] == "error"
        assert result["node_result"].error.code == "NODE_EXCEPTION"
        assert "context exploded" in result["node_result"].error.message
        # Metrics still collected even when error is caught
        assert mm.metrics["validate"].call_count == 1


# ── New middleware integration tests ─────────────────────────────────

class TestMiddlewareInGraph:

    def test_metrics_collected_on_clean_run(self):
        """MetricsMiddleware collects data for all nodes during a clean run."""
        mm = MetricsMiddleware()
        graph = build_conversation_graph(node_middleware=[mm])
        state = _make_state(_CleanContext())

        result = graph.invoke(state)

        snap = mm.snapshot()
        assert "validate" in snap
        assert "reason" in snap
        assert "respond" in snap
        assert snap["validate"]["call_count"] >= 1

    def test_metrics_on_looping_run(self):
        """MetricsMiddleware shows multiple calls when graph loops."""
        mm = MetricsMiddleware()
        graph = build_conversation_graph(node_middleware=[mm])
        state = _make_state(_GappyContext())

        result = graph.invoke(state)

        snap = mm.snapshot()
        assert snap["validate"]["call_count"] == MAX_TURNS
        assert snap["reason"]["call_count"] == MAX_TURNS
        assert snap["respond"]["call_count"] == MAX_TURNS

    def test_logging_middleware_no_crash(self):
        """LoggingMiddleware runs without crashing the graph."""
        graph = build_conversation_graph(node_middleware=[LoggingMiddleware()])
        state = _make_state(_CleanContext())

        result = graph.invoke(state)
        assert result["current_turn"] == 1

    def test_multiple_middleware_compose(self):
        """Multiple middleware compose correctly in the conversation graph."""
        mm = MetricsMiddleware()
        graph = build_conversation_graph(
            node_middleware=[LoggingMiddleware(), mm, ErrorHandlingMiddleware()],
        )
        state = _make_state(_CleanContext())

        result = graph.invoke(state)

        assert "validate" in mm.snapshot()
        assert result["current_turn"] == 1


class TestLLMInjection:

    def test_stub_llm_in_state(self):
        """State can carry an LLM callable (for future use by reason node)."""
        graph = build_conversation_graph()
        state = _make_state(_CleanContext(), llm=call_llm_stub)

        result = graph.invoke(state)

        # Graph still works; llm is just carried in state
        assert result["current_turn"] == 1
        # The llm callable is preserved in state
        assert result.get("llm") is call_llm_stub

    def test_none_llm_in_state(self):
        """State works fine without an LLM (backwards compat)."""
        graph = build_conversation_graph()
        state = _make_state(_CleanContext(), llm=None)

        result = graph.invoke(state)
        assert result["current_turn"] == 1


# ── Pre-flight LLM validation tests ─────────────────────────────────

def _smart_llm(request: LLMRequest) -> LLMResponse:
    """Echoes system prompt — always contains the right concepts."""
    return LLMResponse(content=request.system_prompt, model="smart", success=True)


def _dumb_llm(request: LLMRequest) -> LLMResponse:
    """Always returns irrelevant text."""
    return LLMResponse(content="I like pizza.", model="dumb", success=True)


_SIMPLE_QUIZ = [
    ValidationQuiz(
        question="What node types exist?",
        required_concepts=["goal", "requirement"],
        weight=1.0,
    ),
]


class TestPreflightValidation:

    def test_smart_llm_builds_graph(self):
        """Smart LLM passes preflight — graph builds successfully."""
        graph = build_conversation_graph(
            llm=_smart_llm,
            preflight_quiz=_SIMPLE_QUIZ,
            preflight_system_prompt="The system has goal and requirement types.",
            preflight_threshold=0.5,
        )
        state = _make_state(_CleanContext())
        result = graph.invoke(state)
        assert result["current_turn"] == 1

    def test_dumb_llm_raises_preflight_error(self):
        """Dumb LLM fails preflight — LLMPreflightError is raised."""
        with pytest.raises(LLMPreflightError) as exc_info:
            build_conversation_graph(
                llm=_dumb_llm,
                preflight_quiz=_SIMPLE_QUIZ,
                preflight_system_prompt="irrelevant",
                preflight_threshold=0.5,
            )

        assert exc_info.value.report.weighted_score < 0.5
        assert not exc_info.value.report.passed

    def test_no_quiz_skips_validation(self):
        """Without a quiz, no validation runs — even with an LLM."""
        graph = build_conversation_graph(llm=_dumb_llm)
        state = _make_state(_CleanContext())
        result = graph.invoke(state)
        assert result["current_turn"] == 1

    def test_no_llm_skips_validation(self):
        """Without an LLM, no validation runs — even with a quiz."""
        graph = build_conversation_graph(preflight_quiz=_SIMPLE_QUIZ)
        state = _make_state(_CleanContext())
        result = graph.invoke(state)
        assert result["current_turn"] == 1

    def test_preflight_report_on_error(self):
        """The LLMPreflightError carries the full report."""
        with pytest.raises(LLMPreflightError) as exc_info:
            build_conversation_graph(
                llm=_dumb_llm,
                preflight_quiz=_SIMPLE_QUIZ,
                preflight_system_prompt="",
                preflight_threshold=0.5,
            )

        report = exc_info.value.report
        assert len(report.results) == 1
        assert len(report.llm_responses) == 1
