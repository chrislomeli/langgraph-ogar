"""
tools — Centralized tool definitions for agent consumption.

All tools that agents (LangGraph or otherwise) can call live here.
Each module groups tools by domain:

  - project_tools: Project engine tools (plan, status, context, findings)
  - intent_tools: Sketch → Plan → Compile pipeline tools (M6)
  - music_tools: Rendering and domain tools (M6)
  - persistence_tools: Save/load/list project tools (M7)

Tools are thin wrappers around domain logic. The domain logic itself
lives in its own package (e.g. src/intent/, src/symbolic_music/).

The generic tool infrastructure (ToolSpec, ToolRegistry, LocalToolClient,
ToolResultEnvelope) lives in src/framework/langgraph_ext/tool_client/.
"""
