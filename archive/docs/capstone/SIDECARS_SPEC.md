# OGAR Sidecar Specification
## Observability, Error Policy, Tool Gating, Evaluation & Budgeting

---

# 1. Purpose

This document defines the **Sidecars** that support the Orchestrator-Grade Agent Runtime (OGAR).

Sidecars are:

- First-class architectural interfaces
- Minimal but disciplined implementations
- Orthogonal to core orchestration logic
- Replaceable without rewriting the engine

They exist to ensure:

- Observability
- Predictable failure behavior
- Capability safety
- Behavioral evaluation
- Cost and retry control

They must not become a telemetry platform or infrastructure project.

---

# 2. Design Principles

Sidecars must:

- Be interface-first, not vendor-first
- Be minimal but complete
- Answer specific trust questions
- Remain orthogonal to business logic
- Be testable in isolation
- Avoid feature creep

Sidecars must NOT:

- Contain orchestration logic
- Control workflow branching
- Duplicate LangGraph responsibilities
- Become a monitoring product

---

# 3. Sidecar Components

---

# 3.1 Observability Sidecar

## Skill Demonstrated
Designing observable AI workflows with actionable signals.

## Must Answer

1. Why did this run take this long?
2. Why did this run fail?
3. How many retries occurred?
4. Which tools were called and with what result?
5. Did any invariant fail?

---

## 3.1.1 Event Vocabulary

All observability is built on a fixed event vocabulary.

### Required Base Fields (all events)

- `run_id: str`
- `timestamp: datetime`
- `event_type: str`
- `trace_id: str`
- `span_id: str`
- `parent_span_id: str | null`
- `attributes: dict`

---

## Event Types

### 1. RunStarted
Emitted when a run begins.

Attributes:
- objective_summary
- config_version

---

### 2. RunFinished
Emitted when a run completes (success or failure).

Attributes:
- status (success | failed | aborted)
- total_duration_ms
- total_tool_calls
- total_retries

---

### 3. NodeStarted
Emitted when a graph node begins execution.

Attributes:
- node_name
- step_id (if applicable)

---

### 4. NodeFinished
Emitted when a graph node completes.

Attributes:
- node_name
- status (ok | error | retry)
- duration_ms

---

### 5. ToolCallStarted
Emitted before tool invocation.

Attributes:
- tool_name
- call_id
- risk_level
- idempotency_key

---

### 6. ToolCallFinished
Emitted after tool invocation.

Attributes:
- tool_name
- call_id
- status (ok | error)
- error_type (if any)
- duration_ms

---

### 7. RetryTriggered
Emitted when retry logic activates.

Attributes:
- node_name
- reason
- retry_count
- max_retries

---

### 8. ApprovalRequested
Emitted when a human gate is required.

Attributes:
- reason
- risk_level
- step_id

---

### 9. ApprovalResolved
Emitted when approval decision is made.

Attributes:
- decision (approved | denied)
- reviewer_id

---

### 10. BudgetWarning
Emitted when budget approaches threshold.

Attributes:
- budget_type (tool_calls | retries | tokens | cost_units)
- remaining
- threshold

---

### 11. BudgetExceeded
Emitted when budget is exceeded.

Attributes:
- budget_type
- limit
- attempted_value

---

### 12. InvariantViolation
Emitted when a state invariant fails.

Attributes:
- invariant_name
- description
- severity

---

# 3.1.2 Minimal Trace Model

- A **Trace** represents one run.
- A **Span** represents:
  - Node execution
  - Tool invocation

Spans must nest correctly:
- ToolCall spans are children of Node spans.
- Node spans are children of the Run span.

This mirrors OpenTelemetry semantics without requiring the SDK.

---

# 3.1.3 Run Report

A deterministic function must produce a Run Report containing:

- total_duration_ms
- node_execution_summary
- tool_call_summary
- retry_count
- approval_count
- budget_events
- invariant_violations
- final_status

The report must be computable solely from emitted events.

---

# 3.2 Error Taxonomy & Policy Sidecar

## Skill Demonstrated
Predictable failure handling in probabilistic systems.

---

## Required Error Types

- TransientToolError
- PermanentToolError
- TimeoutError
- SchemaViolationError
- PolicyDeniedError
- BudgetExceededError
- InvariantViolationError
- SystemBugError

---

## Error Policy Mapping

Each error must map deterministically to:

- retry (bounded)
- fail run
- request approval
- downgrade severity
- escalate

Policy must be implemented as a pure mapping function.

No silent exception swallowing.

All errors must emit events.

---

# 3.3 Tool Gating Sidecar

## Skill Demonstrated
Capability safety and deterministic enforcement.

---

## Must Support

Per-step gating based on:

- risk_level
- budget remaining
- environment mode
- feature flags

Denials must:
- include reason codes
- emit PolicyDeniedError
- be testable via scenario harness

Policy logic must not live in tool registry or planner.

---

# 3.4 Evaluation Harness Sidecar

## Skill Demonstrated
Behavioral AI system testing.

---

## Requirements

- ≥ 30 scenario tests
- Fault injection support
- Behavioral assertions:
  - termination
  - bounded retries
  - no forbidden tools
  - no invariant violations
- Deterministic replay support
- Evaluation summary output

---

# 3.5 Budget & Cost Sidecar

## Skill Demonstrated
Production realism and bounded resource control.

---

## Must Enforce

- max tool calls per run
- max retries per step
- max cost units
- optional: token limits

Budgets must:
- emit BudgetWarning events
- emit BudgetExceeded events
- appear in run report

---

# 4. Implementation Level Guidance

To count as implemented:

- Structured events written to JSONL or in-memory sink
- Run report generator
- Typed error classes
- Pure policy functions
- Scenario runner with summary output

Not required:

- Dashboards
- OTEL exporter
- Metrics backend
- Vendor integration

---

# 5. A-Level Completion Checklist

1. Fault injection triggers typed error.
2. Retry logic emits RetryTriggered event.
3. Forbidden tool call emits PolicyDeniedError.
4. BudgetExceeded emits event and stops run.
5. Run report summarizes entire lifecycle deterministically.
6. Evaluation harness reports pass/fail with metrics.

---

# 6. Non-Goals

- Full telemetry infrastructure
- Distributed tracing deployment
- High-scale metric aggregation
- Production alerting systems
- Monitoring dashboards

This sidecar layer exists to ensure trust, not to become a monitoring platform.

---

End of Specification