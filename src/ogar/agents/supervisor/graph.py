"""
ogar.agents.supervisor.graph

Supervisor agent LangGraph graph — supports both stub and LLM modes.

Topology (stub mode — no LLM):
  START
    → fan_out_to_clusters → run_cluster_agent (parallel)
    → assess_situation (stub summary)
    → decide_actions (stub — no commands)
    → dispatch_commands → END

Topology (LLM mode — with tools):
  START
    → fan_out_to_clusters → run_cluster_agent (parallel)
    → assess_situation_llm → [tool_calls] → assess_tool_node → loop
                           → [done] → parse_assessment
    → decide_actions_llm   → [tool_calls] → decide_tool_node → loop
                           → [done] → parse_commands
    → dispatch_commands → END

Usage:
  # Stub mode (default — no API key needed):
  graph = build_supervisor_graph()

  # LLM mode:
  from langchain_openai import ChatOpenAI
  llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
  graph = build_supervisor_graph(llm=llm)

  # With optional HITL gate:
  from ogar.hitl.gate import ConsoleApprovalGate
  graph = build_supervisor_graph(gate=ConsoleApprovalGate())

The Send API pattern
─────────────────────
fan_out_to_clusters returns a list of Send() objects — one per cluster.
Each Send() looks like:
  Send("run_cluster_agent", cluster_agent_state_dict)

LangGraph runs all of them in parallel.  Each one invokes the cluster
agent subgraph with its own isolated state.  Results are merged back
into SupervisorState via the aggregate_findings_reducer.

This is the key LangGraph skill this graph demonstrates:
  "dynamic fan-out where the number of targets is known only at runtime"
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Any, Literal, List, Optional
from uuid import uuid4

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Send

from ogar.actuators.base import ActuatorCommand
from ogar.agents.cluster.graph import cluster_agent_graph
from ogar.agents.cluster.state import ClusterAgentState
from ogar.agents.supervisor.state import SupervisorState
from ogar.hitl.gate import ApprovalRequest, HumanApprovalGate
from ogar.tools.supervisor_tools import (
    SUPERVISOR_TOOLS,
    clear_supervisor_tool_state,
    set_supervisor_tool_state,
)

logger = logging.getLogger(__name__)


# ── System prompts ────────────────────────────────────────────────────────────

ASSESS_SYSTEM_PROMPT = """You are a wildfire monitoring supervisor agent.

You have received anomaly findings from {cluster_count} cluster agent(s):
{cluster_list}

Your job is to assess the overall situation by:
  1. Using tools to examine the findings in detail
  2. Looking for cross-cluster correlations (same anomaly in multiple clusters)
  3. Distinguishing real threats from noise
  4. Writing a concise situation summary

After your analysis, respond with a JSON object (and nothing else):
{{
  "severity": "critical" | "high" | "moderate" | "low" | "none",
  "situation_summary": "Brief description of what is happening",
  "correlated_events": true/false,
  "affected_clusters": ["cluster-id-1", ...],
  "recommended_actions": ["action description", ...]
}}
"""

DECIDE_SYSTEM_PROMPT = """You are a wildfire monitoring supervisor making action decisions.

Situation summary: {situation_summary}

Based on the situation assessment, decide what actuator commands to issue.
Available command types:
  - "alert": Send alerts to operators (payload: {{"message": "...", "recipients": [...]}})
  - "escalate": Escalate to higher authority (payload: {{"reason": "...", "urgency": "high"|"medium"}})
  - "suppress": Suppress a known false positive (payload: {{"finding_ids": [...], "reason": "..."}})
  - "drone_task": Deploy a drone for closer inspection (payload: {{"target_cluster": "...", "task": "inspect"|"monitor"}})

Use the available tools to review findings before deciding.

Respond with a JSON object (and nothing else):
{{
  "commands": [
    {{
      "command_type": "alert" | "escalate" | "suppress" | "drone_task",
      "cluster_id": "target-cluster-id",
      "priority": 1-5,
      "payload": {{ ... }}
    }}
  ],
  "reasoning": "Brief explanation of why these commands were chosen"
}}

If no action is needed, return: {{"commands": [], "reasoning": "No action needed because ..."}}
"""


# ── Node functions ────────────────────────────────────────────────────────────

def fan_out_to_clusters(state: SupervisorState) -> List[Send]:
    """
    Fan out to all active cluster agents using the Send API.

    This node does NOT return a partial state update.
    Instead it returns a list of Send() objects.

    LangGraph interprets a list of Send() objects as: "run all of these
    nodes in parallel, then merge their state changes with the parent."

    Each Send() targets the "run_cluster_agent" node and passes it
    a ClusterAgentState-shaped dict as input.

    This is the dynamic fan-out pattern — the number of clusters is
    determined at runtime from state["active_cluster_ids"].
    If there are 3 active clusters, 3 cluster agents run in parallel.
    If there is 1, only 1 runs.  No code changes.
    """
    cluster_ids = state.get("active_cluster_ids", [])
    logger.info(
        "Supervisor fanning out to %d cluster(s): %s",
        len(cluster_ids),
        cluster_ids,
    )

    sends = []
    for cluster_id in cluster_ids:
        # Build a ClusterAgentState-shaped dict to pass to the subgraph.
        # The subgraph will receive this as its initial state.
        cluster_state: ClusterAgentState = {
            "cluster_id": cluster_id,
            "workflow_id": f"{cluster_id}::supervisor-fanout",
            "sensor_events": [],       # Subgraph will load from Store (future)
            "trigger_event": None,     # TODO: pass the actual trigger event
            "messages": [],
            "anomalies": [],
            "status": "idle",
            "error_message": None,
        }
        sends.append(Send("run_cluster_agent", cluster_state))

    return sends


def run_cluster_agent(state: ClusterAgentState) -> dict:
    """
    Wrapper node that invokes the cluster agent subgraph.

    This node is the target of each Send() from fan_out_to_clusters.
    It receives a ClusterAgentState and invokes the compiled cluster
    agent graph synchronously.

    The results (specifically state["anomalies"]) are mapped back to
    the supervisor's cluster_findings via the graph output mapping.

    Note: LangGraph runs this node once per Send() — so if there are
    3 active clusters, this function runs 3 times in parallel.
    Each invocation has completely isolated state.
    """
    cluster_id = state.get("cluster_id", "unknown")
    logger.info("Supervisor invoking cluster agent for cluster=%s", cluster_id)

    # Invoke the compiled cluster agent subgraph.
    # .invoke() runs the graph to completion and returns the final state.
    result_state = cluster_agent_graph.invoke(state)

    # Return only the fields we want merged into the supervisor's state.
    # The aggregate_findings_reducer on cluster_findings will accumulate
    # the anomalies from all cluster agents.
    return {
        "cluster_findings": result_state.get("anomalies", []),
    }


def assess_situation(state: SupervisorState) -> dict:
    """
    Stub assess_situation node — used when no LLM is provided.

    Produces a placeholder summary from the aggregated findings.
    """
    findings = state.get("cluster_findings", [])
    logger.info(
        "Supervisor assess_situation — STUB — %d finding(s) from clusters",
        len(findings),
    )

    summary = (
        f"[STUB] Received {len(findings)} finding(s) from "
        f"{len(state.get('active_cluster_ids', []))} cluster(s). "
        "Cross-cluster correlation not yet implemented."
    )

    return {
        "situation_summary": summary,
        "status": "deciding",
        "messages": [AIMessage(content=summary)],
    }


def decide_actions(state: SupervisorState) -> dict:
    """
    Stub decide_actions node — used when no LLM is provided.

    Returns no commands and no approval needed.
    """
    logger.info("Supervisor decide_actions — STUB")

    return {
        "pending_commands": [],
        "requires_approval": False,
        "status": "dispatching",
    }


# ── LLM-backed node factories ────────────────────────────────────────────────

def _make_assess_llm_node(llm_with_tools: BaseChatModel):
    """
    Factory that returns an assess_situation node backed by an LLM.

    The LLM uses supervisor tools to examine findings across clusters,
    then produces a structured situation assessment.
    """

    def assess_situation_llm(state: SupervisorState) -> dict:
        findings = state.get("cluster_findings", [])
        cluster_ids = state.get("active_cluster_ids", [])
        messages = state.get("messages", [])

        # Load tool state so tools can access findings.
        set_supervisor_tool_state(findings, cluster_ids)

        logger.info(
            "Supervisor assess_situation — LLM mode (%d findings, %d clusters)",
            len(findings),
            len(cluster_ids),
        )

        # Build initial messages on first call.
        if not messages:
            sys_msg = SystemMessage(
                content=ASSESS_SYSTEM_PROMPT.format(
                    cluster_count=len(cluster_ids),
                    cluster_list=", ".join(cluster_ids),
                )
            )
            finding_lines = []
            for f in findings[:30]:
                finding_lines.append(
                    f"  [{f['anomaly_type']}] cluster={f['cluster_id']} "
                    f"conf={f['confidence']:.2f} — {f['summary'][:80]}"
                )
            user_content = (
                f"Active clusters: {', '.join(cluster_ids)}\n"
                f"Total findings: {len(findings)}\n"
                f"Findings:\n" + "\n".join(finding_lines)
            )
            user_msg = HumanMessage(content=user_content)
            messages = [sys_msg, user_msg]

        response = llm_with_tools.invoke(messages)

        return {
            "messages": [response],
            "status": "assessing",
        }

    return assess_situation_llm


def _parse_assessment(state: SupervisorState) -> dict:
    """
    Parse the LLM's situation assessment into state fields.

    Extracts the JSON from the last AI message and sets situation_summary.
    """
    messages = state.get("messages", [])

    # Find the last AI message with content.
    last_ai = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            last_ai = msg
            break

    if last_ai is None:
        return {
            "situation_summary": "[No assessment produced]",
            "status": "deciding",
        }

    # Try to parse JSON.
    try:
        content = last_ai.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        parsed = json.loads(content)
    except (json.JSONDecodeError, Exception):
        parsed = {
            "severity": "unknown",
            "situation_summary": last_ai.content[:300],
        }

    summary = parsed.get("situation_summary", last_ai.content[:300])

    return {
        "situation_summary": summary,
        "status": "deciding",
    }


def _make_decide_llm_node(llm_with_tools: BaseChatModel):
    """
    Factory that returns a decide_actions node backed by an LLM.

    The LLM reads the situation summary and uses tools to review findings,
    then produces a list of actuator commands.
    """

    def decide_actions_llm(state: SupervisorState) -> dict:
        findings = state.get("cluster_findings", [])
        cluster_ids = state.get("active_cluster_ids", [])
        situation = state.get("situation_summary", "No assessment available")
        messages = state.get("messages", [])

        # Reload tool state for the decide phase.
        set_supervisor_tool_state(findings, cluster_ids)

        logger.info("Supervisor decide_actions — LLM mode")

        # Check if the last message is from the decide phase.
        has_decide_prompt = any(
            isinstance(m, SystemMessage)
            and "action decisions" in (m.content or "")
            for m in messages
        )
        if not has_decide_prompt:
            sys_msg = SystemMessage(
                content=DECIDE_SYSTEM_PROMPT.format(situation_summary=situation)
            )
            user_msg = HumanMessage(
                content=f"Situation: {situation}\n\nDecide what actions to take."
            )
            messages = [sys_msg, user_msg]

        response = llm_with_tools.invoke(messages)

        return {
            "messages": [response],
            "status": "deciding",
        }

    return decide_actions_llm


def _parse_commands(state: SupervisorState) -> dict:
    """
    Parse the LLM's action decision into ActuatorCommands.

    Extracts the JSON command list from the last AI message and
    creates ActuatorCommand objects for dispatch.
    """
    messages = state.get("messages", [])

    # Clean up tool state.
    clear_supervisor_tool_state()

    # Find the last AI message with content.
    last_ai = None
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            last_ai = msg
            break

    if last_ai is None:
        return {
            "pending_commands": [],
            "requires_approval": False,
            "status": "dispatching",
        }

    # Parse JSON.
    try:
        content = last_ai.content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(lines[1:-1])
        parsed = json.loads(content)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("Supervisor: failed to parse LLM decision: %s", exc)
        return {
            "pending_commands": [],
            "requires_approval": False,
            "status": "dispatching",
        }

    # Convert JSON commands to ActuatorCommand objects.
    commands = []
    for cmd in parsed.get("commands", []):
        try:
            commands.append(
                ActuatorCommand.create(
                    command_type=cmd["command_type"],
                    source_agent="supervisor",
                    cluster_id=cmd.get("cluster_id", "unknown"),
                    payload=cmd.get("payload", {}),
                    priority=cmd.get("priority", 3),
                )
            )
        except (KeyError, Exception) as exc:
            logger.warning("Supervisor: skipping invalid command: %s", exc)

    # High-priority commands (4+) may require approval.
    requires_approval = any(c.priority >= 4 for c in commands)

    logger.info(
        "Supervisor decided %d command(s), requires_approval=%s",
        len(commands),
        requires_approval,
    )

    return {
        "pending_commands": commands,
        "requires_approval": requires_approval,
        "status": "dispatching",
    }


async def hitl_pause(state: SupervisorState, *, gate: HumanApprovalGate) -> dict:
    """
    Pause execution for human approval.

    This node is only reached when decide_actions sets requires_approval=True
    AND a gate was provided at build time.

    The gate parameter is injected at graph compile time via partial().
    The graph itself does not hold a reference to the gate —
    this keeps the graph state serialisable (important for checkpointing).
    """
    request_id = str(uuid4())
    logger.info("Supervisor requesting human approval — request_id=%s", request_id)

    request = ApprovalRequest(
        request_id=request_id,
        cluster_id=",".join(state.get("active_cluster_ids", [])),
        situation_summary=state.get("situation_summary", "No summary available"),
        proposed_action=f"Execute {len(state.get('pending_commands', []))} command(s)",
        confidence=0.9,
        context={"finding_count": len(state.get("cluster_findings", []))},
    )

    result = await gate.wait_for_approval(request)

    return {
        "approval_request_id": request_id,
        "approval_decision": {
            "approved": result.approved,
            "reason": result.reason,
            "modifications": result.modifications,
        },
        "status": "dispatching",
    }


def dispatch_commands(state: SupervisorState) -> dict:
    """
    Send actuator commands — placeholder for real actuator dispatch.

    Checks the approval decision if one is required.
    If approved (or no approval needed), dispatches pending_commands.

    TODO: Wire to ActuatorRegistry or publish to commands.actuators Kafka topic.
    """
    decision = state.get("approval_decision")
    if decision is not None and not decision.get("approved", False):
        logger.info(
            "Supervisor: human REJECTED action — reason=%r. Aborting dispatch.",
            decision.get("reason"),
        )
        return {"status": "complete", "pending_commands": []}

    commands = state.get("pending_commands", [])
    logger.info("Supervisor dispatching %d command(s)", len(commands))

    return {"status": "complete"}


# ── Routers ───────────────────────────────────────────────────────────────────

def route_after_assess_llm(
    state: SupervisorState,
) -> Literal["assess_tool_node", "parse_assessment", "__end__"]:
    """
    Router for LLM assess phase — check if the LLM wants to call tools.
    """
    if state.get("status") == "error":
        return "__end__"

    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "assess_tool_node"

    return "parse_assessment"


def route_after_decide_llm(
    state: SupervisorState,
) -> Literal["decide_tool_node", "parse_commands", "__end__"]:
    """
    Router for LLM decide phase — check if the LLM wants to call tools.
    """
    if state.get("status") == "error":
        return "__end__"

    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "decide_tool_node"

    return "parse_commands"


def _make_route_after_decide(has_gate: bool):
    """
    Factory for the route_after_decide conditional edge.

    When a gate is provided, high-priority commands route to hitl_pause.
    When no gate is provided, all commands go directly to dispatch.
    """
    if has_gate:
        def route_after_decide(
            state: SupervisorState,
        ) -> Literal["hitl_pause", "dispatch_commands", "__end__"]:
            if state.get("status") == "error":
                return "__end__"
            if state.get("requires_approval"):
                logger.info("Supervisor routing to HITL pause for human approval")
                return "hitl_pause"
            return "dispatch_commands"
    else:
        def route_after_decide(
            state: SupervisorState,
        ) -> Literal["dispatch_commands", "__end__"]:
            if state.get("status") == "error":
                return "__end__"
            return "dispatch_commands"

    return route_after_decide


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_supervisor_graph(
    llm: Optional[BaseChatModel] = None,
    gate: Optional[HumanApprovalGate] = None,
):
    """
    Compile and return the supervisor graph.

    Parameters
    ──────────
    llm : Optional LangChain chat model.  When provided, assess_situation
          and decide_actions use LLM + ToolNode in a ReAct loop.  When
          None (default), deterministic stubs are used instead.

    gate : Optional HumanApprovalGate.  When provided, high-priority
           commands route through hitl_pause for human approval.
           When None (default), all commands dispatch directly.
    """
    builder = StateGraph(SupervisorState)

    # ── Always-present nodes ─────────────────────────────────────────
    builder.add_node("fan_out_to_clusters", fan_out_to_clusters)
    builder.add_node("run_cluster_agent", run_cluster_agent)
    builder.add_node("dispatch_commands", dispatch_commands)

    builder.add_edge(START, "fan_out_to_clusters")

    if llm is not None:
        # ── LLM mode ─────────────────────────────────────────────────
        llm_with_tools = llm.bind_tools(SUPERVISOR_TOOLS)

        # Assess phase: LLM + tool loop → parse_assessment
        builder.add_node("assess_situation", _make_assess_llm_node(llm_with_tools))
        builder.add_node("assess_tool_node", ToolNode(SUPERVISOR_TOOLS))
        builder.add_node("parse_assessment", _parse_assessment)

        # Decide phase: LLM + tool loop → parse_commands
        builder.add_node("decide_actions", _make_decide_llm_node(llm_with_tools))
        builder.add_node("decide_tool_node", ToolNode(SUPERVISOR_TOOLS))
        builder.add_node("parse_commands", _parse_commands)

        # Wiring: fan_out → cluster agents → assess loop → decide loop
        builder.add_edge("run_cluster_agent", "assess_situation")
        builder.add_conditional_edges("assess_situation", route_after_assess_llm)
        builder.add_edge("assess_tool_node", "assess_situation")
        builder.add_edge("parse_assessment", "decide_actions")
        builder.add_conditional_edges("decide_actions", route_after_decide_llm)
        builder.add_edge("decide_tool_node", "decide_actions")

        # parse_commands → route_after_decide (HITL or dispatch)
        route_fn = _make_route_after_decide(has_gate=gate is not None)
        builder.add_conditional_edges("parse_commands", route_fn)

        logger.info("Supervisor graph compiled (LLM mode)")
    else:
        # ── Stub mode ────────────────────────────────────────────────
        builder.add_node("assess_situation", assess_situation)
        builder.add_node("decide_actions", decide_actions)

        builder.add_edge("run_cluster_agent", "assess_situation")
        builder.add_edge("assess_situation", "decide_actions")

        route_fn = _make_route_after_decide(has_gate=gate is not None)
        builder.add_conditional_edges("decide_actions", route_fn)

        logger.info("Supervisor graph compiled (stub mode)")

    # ── HITL (optional) ──────────────────────────────────────────────
    if gate is not None:
        builder.add_node(
            "hitl_pause",
            functools.partial(hitl_pause, gate=gate),
        )
        builder.add_edge("hitl_pause", "dispatch_commands")

    builder.add_edge("dispatch_commands", END)

    compiled = builder.compile()
    return compiled
