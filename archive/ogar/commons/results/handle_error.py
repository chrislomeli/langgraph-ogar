"""Generic error-handler node for LangGraph graphs."""
from ogar.commons.results.result_schema import NodeResult


def handle_error(state: dict) -> dict:
    """Log the error and mark the run as failed.

    This node is generic — it reads ``node_result`` from state and
    marks ``run_status = "failed"``.  Works with any graph that puts
    a :class:`NodeResult` in ``state["node_result"]``.
    """
    result: NodeResult | None = state.get("node_result")
    if result and not result.ok and result.error:
        print(f"  ✗ Error [{result.error.code}]: {result.error.message}")
        for err in result.error.details.get("errors", []):
            print(f"    field={err.get('loc')} — {err.get('msg')}")
    return {"run_status": "failed"}