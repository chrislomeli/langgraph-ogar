# Next Project Strategy

> Vision document — February 25, 2026

## Context

The symbolic-music project served as a learning vehicle for agentic AI patterns.
Over 12 milestones we built a full LangGraph tutorial progression, a reusable
framework (DAG orchestration, tool registries, observability middleware), and a
domain-specific pipeline (Sketch → Plan → Compile → Render). That work is complete.

This document captures the strategic direction for what comes next.

---

## Key Decisions

### 1. The music project is not a product

There is no viable product in "conversational AI helps you compose symbolic music."
The market is either served by audio-generation tools (Suno/Udio) or by DAW plugins
that don't need an LLM. The niche of "composer who wants to discuss ideas with an AI
and get symbolic output" is too small to pursue.

The music project remains on GitHub as evidence of architectural depth and domain range.
No further active development.

### 2. The next project is a showcase / walkthrough

The goal is a GitHub repository that demonstrates how to take an agentic system from
prototype to production. It serves as:

- **Portfolio piece** — proof of production-grade thinking for employers or clients
- **Teaching material** — potential blog posts, video walkthrough, or course content
- **Pull mechanism** — makes the author findable and credible in the agentic/LLMOps space

### 3. Target audience

Technical — potential employers, consulting clients, or collaborators who want to see
someone who can bridge LLM prototyping and production deployment.

### 4. Career direction

Consulting / fractional technical work is the most natural fit. The unique value
proposition: deep production infrastructure experience (k8s, Kafka, observability, CI/CD)
combined with hands-on agentic AI skills (orchestration, tool use, state management,
human-in-the-loop patterns). This combination is rare in the current market.

---

## The Three-Box Model

The project is decomposed into three independent layers:

### Box 1: Production Scaffolding

The infrastructure that makes an agentic system production-ready.

- Docker Compose for local development
- Kubernetes manifests / Helm charts for deployment
- Kafka for async agent task eventing
- Observability: Prometheus metrics, structured logging, Grafana dashboard
- CI/CD pipeline
- Health checks, cost tracking, failure handling

This is where the bulk of **new learning** happens. It showcases existing
infrastructure skills applied to the LLM domain.

### Box 2: Reusable Framework

Extracted and polished from the symbolic-music project. Domain-independent
agentic infrastructure:

- **PlanOrchestrator** — DAG-based plan lifecycle (draft → approved → executing → done)
- **PlanGraph** — acyclic dependency graph with cycle detection, topological sort
- **SubPlan** — state machine for individual plan steps with invalidation cascades
- **ScopeRegistry** — pluggable planners + executors per scope type
- **ApprovalPolicy** — AlwaysApprove, AlwaysReview, ReviewStructuralChanges
- **ToolSpec / ToolRegistry** — typed tool contracts with JSON Schema / MCP-compatible export
- **LocalToolClient** — validates inputs/outputs, wraps in ToolResultEnvelope (provenance metadata)
- **InstrumentedGraph** — StateGraph subclass with interceptor hooks and middleware
- **StateMediator** — routes tool results to state handlers

Key technique to feature: **structured project state as agent memory**. Instead of
re-reading conversation history, an agent reads a DAG of plans, decisions, and outcomes.
This solves the LLM continuity problem (context loss across sessions) with structure,
not just facts. This is presented as a *technique*, not a product.

### Box 3: Pluggable Use Case

A simple, immediately understandable agentic application that exercises all the patterns.
**Decided last.** Requirements:

- Dead simple domain — no expertise required to understand
- At least 3-4 tools
- Multi-step execution with dependencies (justifies the DAG)
- At least one human-in-the-loop checkpoint (justifies approval policies)
- State that persists across sessions (justifies project state technique)
- Something observable (justifies metrics/logging)

Candidate use cases (not yet chosen):
- **Research assistant** — search → read → synthesize → human review → finalize
- **Content pipeline** — research → outline → draft → review → revise
- **Code review agent** — scan → analyze → report → discuss → re-check

The use case is the **story** (the hook for the README). The infrastructure is the
**spice** (the thing that makes someone think "this person knows what they're doing").

---

## Walkthrough Structure (Tentative)

Each stage builds on the last. Each is runnable. Each teaches something specific.

1. **Notebook prototype** — basic LLM + tools, no infrastructure
2. **Add structure** — state management, tool registry, typed contracts
3. **Add orchestration** — DAG-based planning, approval workflows
4. **Add persistence** — project state survives across sessions
5. **Add observability** — metrics, logging, cost tracking
6. **Deploy** — k8s, Kafka for async tasks, health checks

Each stage could correspond to a Git tag/branch, a blog post, or a video chapter.

---

## What NOT to Build

- Not rebuilding LangGraph or CrewAI — build **on top of** them
- Not a product — this is a showcase and teaching tool
- Not multi-agent swarms — the market is crowded and the pattern is mostly hype
- Not the music project's tool library — that work is done

---

## Relationship to Existing Code

The symbolic-music repo contains the raw material for Box 2. Next steps:

- Extract `src/framework/langgraph_ext/` into a standalone package or new repo
- Clean APIs, improve docstrings, ensure standalone tests pass without music dependencies
- Define the contracts that Box 3 must implement (tool definitions, scope registry entries)
- The music domain code (`src/intent/`, `src/symbolic_music/`, `src/graph/`) stays here

---

## Open Questions

- **New repo or monorepo?** Probably a fresh repo for the showcase project, with the
  framework either as a subpackage or a dependency. TBD.
- **Content format?** Blog posts first (lower effort, faster feedback). Video/course
  only if there's demonstrated demand.
- **Timeline?** Boxes 1 and 2 can be built in parallel with box 3 chosen later.
  Target: framework polished in 1-2 months, production scaffolding in 2-4 months,
  use case integrated by month 5. Content production throughout.

---

## Personal Goals Alignment

| Goal | How this project serves it |
|---|---|
| Learn LLMs / agentic systems | Box 2 (framework) + Box 3 (use case) |
| LLMOps skills (k8s, Kafka) | Box 1 (production scaffolding) — the primary new learning |
| Portfolio / pull | The complete repo + blog posts |
| Consulting credibility | Demonstrates the exact skillset clients need |
| Music / musicianship | Pursued independently — no longer coupled to this project |
