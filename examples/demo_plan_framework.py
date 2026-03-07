#!/usr/bin/env python3
"""
Hello World: Plan Framework Demo

A simple "blog post" project managed by the PlanOrchestrator.

The plan DAG:
    [research] ──► [outline] ──► [writing] ──► [review]

Each sub-plan has a trivial engine (generates dummy content) and
a trivial executor (transforms content into a "result").

Shows:
  1. Building a PlanGraph (DAG of sub-plans)
  2. Registering domain planners and executors
  3. Running the orchestrator to completion (auto-approve)
  4. Running with human-in-the-loop (AlwaysReview)
  5. Refinement: changing "research" and watching downstream invalidate

Usage:
    conda run -n symbolic-music python examples/demo_plan_framework.py
"""

from __future__ import annotations

import sys
sys.path.insert(0, "src")

from framework.langgraph_ext.planning import (
    AlwaysApprove,
    AlwaysReview,
    EventKind,
    OrchestratorEvent,
    PlanGraph,
    PlanOrchestrator,
    RefinementRequest,
    ScopeRegistry,
    SubPlan,
    SubPlanExecutor,
    SubPlanPlanner,
)


# ====================================================================
# STEP 1: Define domain planners and executors
# ====================================================================
# These are the "workers" — they know about the domain (blog posts).
# The framework knows nothing about blogs.

class BlogPlanner(SubPlanPlanner):
    """Generates dummy content for any blog sub-plan."""

    def plan(self, scope_id, plan, context=None):
        templates = {
            "research": "Research notes: DAGs are directed acyclic graphs used in scheduling.",
            "outline":  "Outline: 1) What is a DAG  2) Why DAGs  3) Examples  4) Conclusion",
            "writing":  "Draft: DAGs are everywhere — from Airflow to Git to build systems...",
            "review":   "Review checklist: accuracy, clarity, examples, grammar",
        }
        return templates.get(scope_id, f"Content for {scope_id}")


class BlogExecutor(SubPlanExecutor):
    """Simulates executing a blog sub-plan by transforming its content."""

    def execute(self, sub_plan, plan, context=None):
        # In a real system, this might call an LLM, run a tool, etc.
        # Here we just acknowledge the work.
        upstream_results = []
        deps = plan.dependencies.get(sub_plan.scope_id, set())
        for dep_id in sorted(deps):
            dep = plan.sub_plans[dep_id]
            if dep.result:
                upstream_results.append(f"  (from {dep_id}: {dep.result[:40]}...)")

        result = f"Done: {sub_plan.scope_id} [v{sub_plan.version}]"
        if upstream_results:
            result += "\n" + "\n".join(upstream_results)
        return result


# ====================================================================
# STEP 2: Register with the ScopeRegistry
# ====================================================================

registry = ScopeRegistry()
registry.register("blog", BlogPlanner(), BlogExecutor())


# ====================================================================
# STEP 3: Build a PlanGraph
# ====================================================================

def make_blog_plan() -> PlanGraph:
    """Create the blog post plan DAG."""
    return PlanGraph(
        title="Blog Post: Understanding DAGs",
        sub_plans={
            "research": SubPlan(scope_id="research", scope_type="blog", content="Research notes: placeholder"),
            "outline":  SubPlan(scope_id="outline",  scope_type="blog", content="Outline: placeholder"),
            "writing":  SubPlan(scope_id="writing",  scope_type="blog", content="Draft: placeholder"),
            "review":   SubPlan(scope_id="review",   scope_type="blog", content="Review: placeholder"),
        },
        dependencies={
            "research": set(),
            "outline":  {"research"},
            "writing":  {"outline"},
            "review":   {"writing"},
        },
    )


# ====================================================================
# Helpers
# ====================================================================

def print_event(event: OrchestratorEvent):
    """Pretty-print orchestrator events."""
    icon = {
        EventKind.plan_proposed:        "📋",
        EventKind.sub_plan_auto_approved: "✅",
        EventKind.sub_plan_approved:    "👍",
        EventKind.sub_plan_executing:   "⚙️ ",
        EventKind.sub_plan_done:        "✔️ ",
        EventKind.sub_plan_failed:      "❌",
        EventKind.sub_plan_stale:       "🔄",
        EventKind.sub_plan_planned:     "📝",
        EventKind.refinement_applied:   "🔧",
        EventKind.plan_complete:        "🎉",
        EventKind.awaiting_approval:    "⏳",
        EventKind.step_no_progress:     "⚠️ ",
    }.get(event.kind, "  ")
    scope = f" [{event.scope_id}]" if event.scope_id else ""
    detail = f" — {event.detail}" if event.detail else ""
    print(f"  {icon} {event.kind.value}{scope}{detail}")


def print_plan_status(plan: PlanGraph):
    """Show the status of every sub-plan."""
    print(f"\n  Plan: {plan.title}")
    print(f"  {'Scope':<12} {'Status':<12} {'Version':<8} Content (first 50 chars)")
    print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*50}")
    for sid in ["research", "outline", "writing", "review"]:
        sp = plan.sub_plans.get(sid)
        if sp:
            content_preview = str(sp.content)[:50] if sp.content else "(none)"
            print(f"  {sp.scope_id:<12} {sp.status.value:<12} v{sp.version:<7} {content_preview}")


# ====================================================================
# Demo 1: Auto-approve — run to completion
# ====================================================================

def demo_auto_approve():
    print("\n" + "=" * 60)
    print("  DEMO 1: Auto-Approve — Full Autonomous Run")
    print("=" * 60)

    orch = PlanOrchestrator(
        registry=registry,
        approval_policy=AlwaysApprove(),
        on_event=print_event,
    )
    orch.load_plan(make_blog_plan())
    print_plan_status(orch.plan)

    print("\n  Running orchestrator...\n")
    result = orch.run()

    print_plan_status(orch.plan)
    print(f"\n  Complete: {result.complete}")


# ====================================================================
# Demo 2: Human-in-the-loop — approve one at a time
# ====================================================================

def demo_human_in_the_loop():
    print("\n" + "=" * 60)
    print("  DEMO 2: Human-in-the-Loop — Step-by-Step Approval")
    print("=" * 60)

    orch = PlanOrchestrator(
        registry=registry,
        approval_policy=AlwaysReview(),
        on_event=print_event,
    )
    orch.load_plan(make_blog_plan())

    step_num = 0
    while not orch.is_complete:
        step_num += 1
        result = orch.step()

        if result.awaiting_approval:
            print(f"\n  --- Human reviews and approves: {result.awaiting_approval} ---")
            for sid in result.awaiting_approval:
                orch.approve(sid)

        if result.no_progress:
            print("  No progress — something is stuck.")
            break

    print_plan_status(orch.plan)
    print(f"\n  Complete after {step_num} steps")


# ====================================================================
# Demo 3: Refinement — change research, watch cascade
# ====================================================================

def demo_refinement():
    print("\n" + "=" * 60)
    print("  DEMO 3: Refinement — Change Research, Watch Cascade")
    print("=" * 60)

    orch = PlanOrchestrator(
        registry=registry,
        on_event=print_event,
    )
    orch.load_plan(make_blog_plan())

    print("\n  --- Initial run ---\n")
    orch.run()
    print_plan_status(orch.plan)

    print("\n  --- Refining 'research' (new topic!) ---\n")
    req = RefinementRequest(
        prompt="Actually, focus on DAGs in LLM agent orchestration",
        target_scopes=frozenset({"research"}),
    )
    invalidated = orch.refine(req)
    print(f"\n  Invalidated: {invalidated}")
    print_plan_status(orch.plan)

    print("\n  --- Re-running after refinement ---\n")
    orch.run()
    print_plan_status(orch.plan)
    print(f"\n  Complete: {orch.is_complete}")
    print(f"  Research is now v{orch.plan.sub_plans['research'].version}")


# ====================================================================
# Main
# ====================================================================

if __name__ == "__main__":
    demo_auto_approve()
    demo_human_in_the_loop()
    demo_refinement()

    print("\n" + "=" * 60)
    print("  KEY TAKEAWAYS")
    print("=" * 60)
    print("""
  1. The framework knows nothing about blogs — domain logic is
     in BlogPlanner and BlogExecutor, registered via ScopeRegistry.

  2. The orchestrator manages the DAG lifecycle: auto-approve or
     human-in-the-loop, step-by-step or run-to-completion.

  3. Refinement is automatic: change one sub-plan, downstream
     dependents are invalidated and re-executed.

  4. Events let you observe everything without coupling to the
     orchestrator internals.

  5. No LLM needed for any of this — it's pure Python infrastructure.
     An LLM would plug in as a engine or executor, not as the
     project manager.
""")
