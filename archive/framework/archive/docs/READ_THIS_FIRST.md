# Orchestrator-Worker — Design Notes

> **Canonical example: `orchestrator_lab_interceptor.ipynb`**
>
> Start there. Everything below explains *why* we landed on that design.

---

## Design Evolution

| Iteration | File | What it does | Status |
|---|---|---|---|
| v1 — Course original | `orchestrator_lab.ipynb` | Bare orchestrator-worker, no ops concerns | **Archived** — learning exercise |
| v2 — Layered + `wrap_node()` | `orchestrator_lab_layered.ipynb` | 4-layer arch, free-function `wrap_node()` wraps nodes with retry/tags | **Superseded** — see problems below |
| v3 — Learning notes | `orchestrator_lab_learning.ipynb` | Exploratory notes | **Archived** |
| **v4 — Interceptor + chain-level ops** | **`orchestrator_lab_interceptor.ipynb`** | `InstrumentedGraph` subclass + retry on chains | **Current** |

---

## Why v2 (`wrap_node`) Was Replaced

The layered notebook put retry/fallback on the **node Runnable** via a `wrap_node()` free function:

```python
add_node(builder, "orchestrator", orchestrator, retry=True)
```

Problems:

1. **Retry targets the wrong thing.** If the node fails for *any* reason (including a bug in state-packing logic), the entire node retries. You almost always want to retry only the LLM/API call.
2. **Not enforceable.** Nothing stops you from calling `builder.add_node()` directly and bypassing `wrap_node()`.
3. **Mixed concerns.** `wrap_node()` handled both universal observability (tags/metadata) *and* per-capability ops (retry/fallback) in one function.

---

## Current Design (v4)

Three clean layers, each with a single responsibility:

### 1. Chains / Tools — per-capability ops

Retry, fallback, caching, rate-limiting go **on the chain or tool** — the thing that actually talks to the LLM or external API.

```python
planner_pipe = (dish_prompt | llm.with_structured_output(Dishes)).with_retry(stop_after_attempt=3)
chef_pipe    = (chef_prompt | llm).with_retry(stop_after_attempt=3)
```

### 2. Node functions — pure business logic

Nodes are plain functions: `state → partial state update`. No ops awareness.

```python
def orchestrator(state: State) -> dict:
    result = planner_pipe.invoke({"meals": state["meals"]})
    return {"sections": result.sections}
```

### 3. Graph — universal cross-cutting via `InstrumentedGraph`

Subclass `StateGraph`. Override `add_node()` to wrap every node with interceptor hooks. Logging, metrics, tracing fire automatically — no opt-in required.

```python
graph = InstrumentedGraph(State, interceptors=[LoggingInterceptor(), MetricsInterceptor()])
graph.add_node("orchestrator", orchestrator)   # plain function, automatically instrumented
```

### Where each concern lives

| Concern | Belongs on | Why |
|---|---|---|
| Retry / fallback | Chain or tool (`.with_retry()`) | The LLM call throws 429/5xx, not the node |
| Caching | Chain or tool | You're caching the expensive operation |
| Rate limiting | LLM client or tool decorator | The API has the limit |
| Logging, metrics, tracing | `InstrumentedGraph` interceptor | Universal, applies to all nodes |
| Run tags / metadata | `make_run_config()` at invocation | Per-run, not per-node |

---

## Interceptor Design Decisions

The `InstrumentedGraph` in the notebook incorporates these choices:

- **`functools.wraps`** instead of manual `__name__`/`__doc__` copy — preserves `__module__`, `__qualname__`, `__wrapped__`
- **Defensive try/except** around every interceptor hook — a broken interceptor cannot crash the graph
- **Thread-safe `MetricsInterceptor`** — keyed by `(node_name, thread_id)` with a lock, safe for parallel `Send()` fan-outs
- **Forward-compatible `add_node(**kwargs)`** — passes through any future LangGraph parameters

### When to use interceptors vs. decorators

| Pattern | Use for | Examples |
|---|---|---|
| **Interceptors** (on graph) | Universal concerns that apply to *every* node | Logging, metrics, tracing, state validation |
| **Decorators / `.with_*()`** (on chain/tool) | Selective per-capability concerns | Retry, cache, rate-limit, fallback |

---

## Pitfalls to Remember

- **Don't mutate state in interceptors** — they observe, they don't act
- **Don't store mutable state carelessly** — use `threading.local()` or key by thread ID for concurrent execution
- **Don't let interceptors raise** — wrap hooks in try/except (the `InstrumentedGraph` does this for you)

---

## Infrastructure (Outside the Graph)

These concerns live at the deployment/platform level, not in LangGraph code:

| Concern | Where | Example |
|---|---|---|
| Request-level timeouts | HTTP server, task queue | FastAPI `timeout`, Celery `time_limit` |
| Rate limiting (hard) | API gateway | Kong, AWS API Gateway |
| Circuit breakers | Service mesh | Stop calling a down provider |
| Secrets | Env vars, vault | `.env`, AWS Secrets Manager |
| Scaling | Worker pools, k8s | Celery, Ray, k8s HPA |
| Persistence | LangGraph checkpointer | `SqliteSaver`, `PostgresSaver` |