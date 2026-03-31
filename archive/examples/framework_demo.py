"""
Framework Demo — One node, one tool, print-based interceptors, StateMediator.

Run:  conda run -n symbolic-music python examples/framework_demo.py

This walks through the full data flow:

  1. Graph has ONE node: "do_work"
  2. That node calls ONE tool: "add_numbers" (via LocalToolClient)
  3. The tool returns a ToolResultEnvelope (content + structured + metadata)
  4. Two interceptors OBSERVE (just print):
       - PrintBeforeInterceptor  → prints when a node starts
       - PrintAfterInterceptor   → prints when a node finishes
  5. A StateMediator TRANSFORMS the result:
       - It sees the envelope's tool_name == "add_numbers"
       - It routes to a handler that pulls the result out of the
         envelope and writes it into the state as 'answer'

The key insight:
  - The TOOL doesn't know about graph state (it just adds numbers)
  - The NODE doesn't know how to update state (it just calls the tool)
  - The MEDIATOR bridges the gap (it reads the envelope metadata
    and decides what state fields to set)
"""

from __future__ import annotations

from typing import Any, TypedDict

# ── Framework imports ───────────────────────────────────────────────

from framework.langgraph_ext.instrumented_graph import (
    InstrumentedGraph,
    Interceptor,
)
from framework.langgraph_ext.middleware.state_mediator import StateMediator
from framework.langgraph_ext.tool_client import (
    LocalToolClient,
    ToolRegistry,
    ToolResultEnvelope,
    ToolSpec,
)
from pydantic import BaseModel


# ====================================================================
# STEP 1: Define the graph state
# ====================================================================
# This is what LangGraph tracks. Nodes return dicts that update it.

class DemoState(TypedDict):
    a: int
    b: int
    answer: int          # ← the mediator will fill this in
    tool_used: str       # ← the mediator will fill this in too


# ====================================================================
# STEP 2: Define a dummy tool (pure function, knows nothing about state)
# ====================================================================

class AddInput(BaseModel):
    x: int
    y: int


class AddOutput(BaseModel):
    sum: int


def add_numbers_handler(inp: AddInput) -> AddOutput:
    """Pure function: adds two numbers. That's it."""
    return AddOutput(sum=inp.x + inp.y)


ADD_TOOL = ToolSpec(
    name="add_numbers",
    description="Add two integers together.",
    input_model=AddInput,
    output_model=AddOutput,
    handler=add_numbers_handler,
)

# the registry is the tool server
registry = ToolRegistry()
registry.register(ADD_TOOL)

# ====================================================================
# STEP 3: Create the tool client (registers the tool, enforces envelope)
# ====================================================================
tool_client = LocalToolClient(registry)


# ====================================================================
# STEP 4: Define interceptors (observe only — just print)
# ====================================================================

class PrintBeforeInterceptor(Interceptor):
    """Prints when a node is about to run."""

    def before(self, node_name: str, state: Any) -> None:
        print(f"  [BEFORE] Node '{node_name}' starting. State: a={state['a']}, b={state['b']}")

    def after(self, node_name: str, state: Any, result: Any) -> None:
        pass  # we'll use a separate interceptor for after

    def on_error(self, node_name: str, state: Any, error: Exception) -> None:
        print(f"  [ERROR]  Node '{node_name}' failed: {error}")


class PrintAfterInterceptor(Interceptor):
    """Prints when a node finishes."""

    def before(self, node_name: str, state: Any) -> None:
        pass

    def after(self, node_name: str, state: Any, result: Any) -> None:
        # At this point 'result' is whatever the node returned
        # (before middleware transforms it)
        if isinstance(result, ToolResultEnvelope):
            print(f"  [AFTER]  Node '{node_name}' returned envelope from tool '{result.meta.tool_name}'")
            print(f"           Structured: {result.structured}")
            print(f"           Content: {result.content[0].text if result.content else '(none)'}")
            print(f"           Duration: {result.meta.duration_ms:.3f}ms")
        else:
            print(f"  [AFTER]  Node '{node_name}' returned: {result}")

    def on_error(self, node_name: str, state: Any, error: Exception) -> None:
        pass


# ====================================================================
# STEP 5: Define the StateMediator (transforms tool results → state)
#  This version maps a tool nane/id to a handler function
# ====================================================================

def handle_add_result(
    node_name: str,
    state: Any,
    envelope: ToolResultEnvelope,
) -> dict[str, Any]:
    """
    This handler knows:
      - The "add_numbers" tool returns {"sum": N}
      - We want to store that as "answer" in the graph state
      - We also record which tool produced it

    The mediator calls this ONLY when it sees tool_name == "add_numbers".
    """
    print(f"  [MEDIATOR] Routing '{envelope.meta.tool_name}' → writing answer={envelope.structured['sum']}")
    return {
        "answer": envelope.structured["sum"],
        "tool_used": envelope.meta.tool_name,
    }


mediator = StateMediator()
mediator.register("add_numbers", handler=handle_add_result)


# ====================================================================
# STEP 6: Define the node (thin — just calls the tool)
# ====================================================================

def do_work(state: DemoState) -> ToolResultEnvelope:
    """
    The node's ONLY job: call the tool and return the envelope.
    It does NOT update state directly — the mediator handles that.
    """
    print(f"  [NODE]   do_work() calling tool 'add_numbers' with x={state['a']}, y={state['b']}")
    envelope = tool_client.call("add_numbers", {"x": state["a"], "y": state["b"]})
    return envelope


# ====================================================================
# STEP 7: Wire the graph
# ====================================================================

graph = InstrumentedGraph(
    DemoState,
    interceptors=[PrintBeforeInterceptor(), PrintAfterInterceptor()],
    middleware=[mediator],
)

graph.add_node("do_work", do_work)
graph.set_entry_point("do_work")
graph.set_finish_point("do_work")

app = graph.compile()


# ====================================================================
# STEP 8: Run it!
# ====================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Framework Demo: One node, one tool, interceptors + mediator")
    print("=" * 60)
    print()

    initial_state = {"a": 7, "b": 35, "answer": 0, "tool_used": ""}

    print(f"Input:  a={initial_state['a']}, b={initial_state['b']}")
    print()
    print("Execution trace:")

    final_state = app.invoke(initial_state)

    print()
    print(f"Output: answer={final_state['answer']}, tool_used='{final_state['tool_used']}'")
    print()

    # ── Recap the flow ──
    print("What happened:")
    print("  1. Graph invoked with a=7, b=35")
    print("  2. PrintBeforeInterceptor observed the node starting")
    print("  3. do_work() called tool_client.call('add_numbers', {x:7, y:35})")
    print("  4. LocalToolClient validated input, ran handler, wrapped result in envelope")
    print("  5. PrintAfterInterceptor observed the envelope (tool_name, structured, duration)")
    print("  6. StateMediator saw tool_name='add_numbers', routed to handle_add_result()")
    print("  7. handle_add_result() returned {answer: 42, tool_used: 'add_numbers'}")
    print("  8. LangGraph applied that dict to state")
    print()
    print("Key point: The tool, node, and state logic are all decoupled.")
    print("  - Tool knows nothing about graph state")
    print("  - Node knows nothing about which state fields to update")
    print("  - Mediator bridges the gap using envelope metadata")
