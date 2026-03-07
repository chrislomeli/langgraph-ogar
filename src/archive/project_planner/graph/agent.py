"""
LangGraph agent for the project engine.

A simple ReAct-style agent: LLM decides which tool to call,
tool executor runs it, results go back to the LLM.
"""

from __future__ import annotations

from typing import Literal

from gqlalchemy import Memgraph
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode

from tools.project_tools import build_project_tools


SYSTEM_PROMPT = """\
You are a project planning assistant. You help manage tasks, milestones, \
dependencies, and outcomes.

{domain_hint}

## Workflow Phases

Every project follows four phases. Always check the current phase with \
get_context_tool before acting. Respect the phase discipline:

### 1. EXPLORING (default)
- Ask clarifying questions about the request
- Record findings as notes (add_finding_tool) against the root milestone
- Do NOT create tasks yet — only gather information
- When you have enough understanding, tell the user you're ready to propose a plan \
and call set_phase_tool to move to "planning"

### 2. PLANNING
- Use propose_plan_tool to create items in "proposed" state
- Use depends_on_index to express ordering within the batch (0-based)
- Present the proposed plan to the user for review
- Do NOT start executing — wait for the user to approve
- When the user approves, call approve_plan_tool (approves all proposed items \
and assigns them), then call set_phase_tool to move to "executing"

### 3. EXECUTING
- Use get_next_actions_tool to see what's actionable
- Use update_status_tool to mark items active/done as work progresses
- Use add_finding_tool to record notes and artifacts
- Use plan_task_tool if new tasks emerge during execution
- When all tasks are done, call set_phase_tool to move to "reviewing"

### 4. REVIEWING
- Use get_context_tool to verify all milestones and outcomes
- Summarize what was accomplished
- Identify any remaining issues

## Rules
- Always check project context before making changes.
- Be concise.
- Priorities: 1-100, higher = more important.
- When using plan_task_tool with dependencies, create tasks one at a time \
so you can use real IDs. Never guess IDs.
- When assigning via plan_task_tool, pass assign_to="self".
"""


def build_agent(
    db: Memgraph,
    project_id: str,
    actor_id: str,
    model_name: str = "gpt-4o-mini",
    domain_hint: str = "This is a general project.",
):
    """
    Build and compile a LangGraph agent for project planning.

    Args:
        db: Memgraph connection
        project_id: Project to operate on (injected into all tools)
        actor_id: Actor performing actions (injected into all tools)
        model_name: OpenAI model to use
        domain_hint: Domain-specific context injected into the system prompt

    Returns:
        Compiled LangGraph app
    """
    tools = build_project_tools(db, project_id, actor_id)
    prompt = SYSTEM_PROMPT.format(domain_hint=domain_hint)
    llm = ChatOpenAI(model=model_name).bind_tools(tools)

    def agent_node(state: MessagesState) -> dict:
        messages = state["messages"]
        # Prepend system prompt if not already there
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=prompt)] + list(messages)
        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> Literal["tools", "__end__"]:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return "__end__"

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    return graph.compile()
