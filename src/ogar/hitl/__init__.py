"""
ogar.hitl

Human-in-the-loop approval gates.

This package provides the abstraction for pausing automated
actions and requesting human approval before proceeding.

  - HumanApprovalGate (gate.py)     — the ABC defining the interface.
  - ConsoleApprovalGate (stub.py)   — asyncio.Event-based stub for
    local dev.  Prints to console, waits for respond() call.
  - (future) TemporalApprovalGate   — uses Temporal wait_for_signal().

The gate pattern was chosen over LangGraph's interrupt() because
interrupt() exits the graph and requires a restart, which is clunky
for synchronous / demo scenarios.
"""