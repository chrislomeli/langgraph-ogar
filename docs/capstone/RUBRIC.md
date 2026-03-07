# LangGraph Expert Capstone
## Orchestrator-Grade Agent Runtime (OGAR)

---

# 1. Objective

Design and implement a **production-grade AI orchestration system** using LangGraph.

This capstone evaluates mastery of:

- Deterministic orchestration of probabilistic reasoning
- Typed state modeling with invariant enforcement
- Tool contract engineering
- Failure handling and bounded retries
- Durable execution and resume
- Structured observability
- Behavioral scenario-based evaluation

The domain is irrelevant. Architectural rigor is the focus.

---

# 2. System Requirements

## 2.1 Core Capabilities

The system must:

- Plan multi-step work
- Execute tools under strict contracts
- Verify tool outputs
- Retry bounded failures
- Dynamically gate tool availability
- Support approval gates
- Persist state across crashes
- Produce structured audit logs
- Run automated scenario-based evaluations

Tools may be deterministic stubs.

---

# 3. Architecture Requirements

## 3.1 Typed State Model

State must include:

- Run metadata
- Task definition
- Plan (steps, revision count)
- Tool requests/responses
- Control state (status, retries, budgets)
- Audit log (append-only)

State must:

- Enforce invariants
- Prevent implicit mutation
- Correlate tool requests to responses
- Validate retry bounds
- Preserve audit history

---

## 3.2 Graph Structure

Required nodes:

- intake
- planner
- tool_selection / gating
- tool_execution
- verification
- decision / branching
- finalize

All transitions must be explicit.
No hidden control loops inside prompts.

---

## 3.3 Tool Contract Framework

Minimum 5 tools (stubbed allowed):

Each tool must define:

- Input schema
- Output schema
- Error schema
- Idempotency support
- Fault injection modes

System must handle:

- Transient failure
- Permanent failure
- Schema violations
- Timeouts
- Partial output

---

## 3.4 Dynamic Tool Gating

Tool availability must depend on:

- Risk level
- Budget constraints
- Task metadata
- Environment mode

Policy logic must be separate from planner logic.

---

## 3.5 Durable Execution

Must support:

- Checkpointing
- Crash + resume
- Idempotent write protection
- Demonstrable mid-run recovery

---

## 3.6 Observability

System must produce:

- Structured event logs
- Tool call correlation logs
- Node execution timing
- Run summary report

Audit trail must support replay.

---

## 3.7 Evaluation Harness

Must include automated scenario suite covering:

- Normal execution
- Tool timeouts
- Schema violations
- Retry scenarios
- Approval gates
- Budget exhaustion
- Plan revision

Harness must:

- Assert termination states
- Detect invariant violations
- Enforce retry bounds
- Support deterministic replay under fixed seed

Manual testing is insufficient.

---

# 4. Prohibited Patterns

- Implicit LLM-driven control flow
- Unbounded retries
- Global mutable state
- Hidden side effects
- Catch-all exception suppression
- Domain-specific shortcuts

---

# 5. Deliverables

- Source repository
- README explaining architecture
- Evaluation report
- Demo script showing:
  - Normal run
  - Crash + resume
  - Fault injection scenario

---

# 6. Grading Rubric

## 6.1 State Modeling & Invariants (15%)

**A:** Typed schema, invariant enforcement, reducer clarity, append-only audit, explicit validation.  
**B:** Typed state but weak invariants or unclear reducers.  
**C:** Ad-hoc state, no validation.

---

## 6.2 Deterministic Orchestration (15%)

**A:** Clear planner/executor/verifier separation. Explicit transitions. Bounded retries.  
**B:** Partial separation. Some control embedded in nodes.  
**C:** LLM controls flow implicitly.

---

## 6.3 Tool Contract Engineering (15%)

**A:** Strict schemas, ID correlation, idempotency, fault injection, typed error handling.  
**B:** Schemas present but inconsistently enforced.  
**C:** Loose tool definitions, unpredictable failure behavior.

---

## 6.4 Dynamic Tool Gating (10%)

**A:** Per-step tool gating. Risk and budget enforcement. Policy separate from planner.  
**B:** Hardcoded or partially enforced gating.  
**C:** All tools globally available.

---

## 6.5 Durable Execution (10%)

**A:** Crash recovery demonstrated. Idempotency verified.  
**B:** Persistence present but fragile.  
**C:** No resume support.

---

## 6.6 Evaluation Harness (15%)

**A:** ≥30 scenarios. Fault injection. Deterministic replay. Behavioral assertions.  
**B:** Limited scenarios. Partial failure testing.  
**C:** Manual testing only.

---

## 6.7 Observability (10%)

**A:** Structured event logs. Span hierarchy. Tool correlation. Metrics aggregation. Replay capability.  
**B:** Logging present but inconsistent.  
**C:** Print statements only.

---

## 6.8 Code Organization (10%)

**A:** Clear modular boundaries. Config externalized. Clean repo structure.  
**B:** Functional but cluttered.  
**C:** Monolithic structure.

---

# 7. Qualitative Design Defense (Required)

Student must defend:

1. Where is the LLM appropriate vs deterministic logic?
2. Where could hallucination occur?
3. How are retries bounded?
4. What is the most fragile component?
5. What happens under adversarial prompting?
6. What would you remove if cost doubled?
7. How would this scale in production?

---

# 8. Testing Philosophy

AI systems require behavioral testing.

Three layers must be demonstrated:

### 8.1 Deterministic Infrastructure Tests
State transitions, retries, gating, invariants.

### 8.2 Contract Boundary Tests
Schema validation, tool-call matching, malformed output handling.

### 8.3 Behavioral Scenario Tests
Termination guarantees, bounded retries, policy enforcement, recovery under fault injection.

Exact text output is not the evaluation metric.
System behavior is.

---

# 9. Observability Specification (OTel-Aligned Stub)

## 9.1 Trace Model

- Trace = one graph run
- Span = node execution or tool call

Each span must record:

- trace_id
- span_id
- parent_span_id
- name
- start_time
- end_time
- duration_ms
- status
- attributes (retry_count, budget_remaining, error_type, etc.)

---

## 9.2 Metrics

Must aggregate:

- total_runs
- failed_runs
- retries_total
- tool_calls_total
- tool_failures_total
- approval_gates_triggered
- average_duration_ms
- p95_duration_ms
- p99_duration_ms

Implementation may stub OTel concepts without SDK integration.

---

# 10. Learning Outcomes

Upon completion, student demonstrates:

- Mastery of LangGraph orchestration
- Engineering guardrails around LLM reasoning
- Durable workflow design
- Evaluation-first AI development
- Production-grade observability thinking

---

End of Assignment