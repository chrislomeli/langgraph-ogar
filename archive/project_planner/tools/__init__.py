"""
High-level tool handlers for the project engine.

These compose Layer 1 (CRUD) and Layer 2 (facade) calls into
agent-friendly operations. Each function takes a Pydantic input model
and returns a Pydantic output model.

No dependency on framework/tool_client — these are plain functions.
Wire to ToolSpec later when you have an agent.
"""
