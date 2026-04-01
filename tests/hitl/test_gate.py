"""Tests for ogar.hitl — ConsoleApprovalGate async pause/resume."""

import asyncio

import pytest

from ogar.hitl.gate import ApprovalRequest, ApprovalResult, HumanApprovalGate
from ogar.hitl.stub import ConsoleApprovalGate


@pytest.fixture
def gate():
    return ConsoleApprovalGate()


def _make_request(request_id: str = "req-1") -> ApprovalRequest:
    return ApprovalRequest(
        request_id=request_id,
        cluster_id="cluster-north",
        situation_summary="Fire detected near grid C4",
        proposed_action="Deploy suppression to C4",
        confidence=0.9,
        context={"finding_count": 3},
    )


def _make_result(request_id: str = "req-1", approved: bool = True) -> ApprovalResult:
    return ApprovalResult(
        request_id=request_id,
        approved=approved,
        reason="Looks correct",
    )


class TestApprovalModels:
    def test_approval_request_fields(self):
        req = _make_request()
        assert req.request_id == "req-1"
        assert req.confidence == 0.9
        assert req.context == {"finding_count": 3}

    def test_approval_result_fields(self):
        res = _make_result()
        assert res.request_id == "req-1"
        assert res.approved is True
        assert res.reason == "Looks correct"

    def test_approval_result_default_modifications(self):
        res = ApprovalResult(request_id="r1", approved=True)
        assert res.modifications == {}

    def test_human_approval_gate_is_abstract(self):
        with pytest.raises(TypeError):
            HumanApprovalGate()


class TestConsoleApprovalGate:
    @pytest.mark.asyncio
    async def test_wait_and_respond(self, gate):
        """Basic flow: wait_for_approval suspends, respond unblocks it."""
        request = _make_request("req-100")

        async def approve_after_delay():
            await asyncio.sleep(0.05)
            await gate.respond(_make_result("req-100", approved=True))

        asyncio.create_task(approve_after_delay())
        result = await asyncio.wait_for(
            gate.wait_for_approval(request), timeout=2.0
        )
        assert result.approved is True
        assert result.request_id == "req-100"

    @pytest.mark.asyncio
    async def test_rejection(self, gate):
        request = _make_request("req-200")

        async def reject():
            await asyncio.sleep(0.05)
            await gate.respond(ApprovalResult(
                request_id="req-200", approved=False, reason="Not sure"
            ))

        asyncio.create_task(reject())
        result = await asyncio.wait_for(
            gate.wait_for_approval(request), timeout=2.0
        )
        assert result.approved is False
        assert result.reason == "Not sure"

    @pytest.mark.asyncio
    async def test_respond_unknown_request_discarded(self, gate):
        """Responding to a non-existent request should not raise."""
        await gate.respond(_make_result("no-such-id"))

    @pytest.mark.asyncio
    async def test_pending_request_ids(self, gate):
        assert gate.pending_request_ids() == []
        request = _make_request("req-300")

        async def delayed_respond():
            await asyncio.sleep(0.1)
            assert "req-300" in gate.pending_request_ids()
            await gate.respond(_make_result("req-300"))

        asyncio.create_task(delayed_respond())
        await asyncio.wait_for(gate.wait_for_approval(request), timeout=2.0)
        assert gate.pending_request_ids() == []

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(self, gate):
        """Two requests pending at the same time, resolved independently."""
        req_a = _make_request("req-A")
        req_b = _make_request("req-B")

        async def respond_both():
            await asyncio.sleep(0.05)
            await gate.respond(_make_result("req-B", approved=False))
            await asyncio.sleep(0.02)
            await gate.respond(_make_result("req-A", approved=True))

        asyncio.create_task(respond_both())

        result_a, result_b = await asyncio.gather(
            asyncio.wait_for(gate.wait_for_approval(req_a), timeout=2.0),
            asyncio.wait_for(gate.wait_for_approval(req_b), timeout=2.0),
        )
        assert result_a.approved is True
        assert result_b.approved is False

    @pytest.mark.asyncio
    async def test_modifications_passed_through(self, gate):
        request = _make_request("req-mod")

        async def respond_with_mods():
            await asyncio.sleep(0.05)
            await gate.respond(ApprovalResult(
                request_id="req-mod",
                approved=True,
                modifications={"target_grid": "C5"},
            ))

        asyncio.create_task(respond_with_mods())
        result = await asyncio.wait_for(
            gate.wait_for_approval(request), timeout=2.0
        )
        assert result.modifications == {"target_grid": "C5"}
