"""
Tests for ToolSpec, ToolRegistry, and LocalToolClient.

No dependency on symbolic_music or intent.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from framework.langgraph_ext.tool_client import (
    LocalToolClient,
    ToolRegistry,
    ToolResultEnvelope,
    ToolSpec,
)


# ── Example tool models ─────────────────────────────────────────────

class AddInput(BaseModel):
    a: int
    b: int


class AddOutput(BaseModel):
    result: int


def add_handler(inp: AddInput) -> AddOutput:
    return AddOutput(result=inp.a + inp.b)


class GreetInput(BaseModel):
    name: str = "world"


class GreetOutput(BaseModel):
    message: str


def greet_handler(inp: GreetInput) -> GreetOutput:
    return GreetOutput(message=f"Hello, {inp.name}!")


ADD_TOOL = ToolSpec(
    name="add",
    description="Add two integers.",
    input_model=AddInput,
    output_model=AddOutput,
    handler=add_handler,
)

GREET_TOOL = ToolSpec(
    name="greet",
    description="Return a greeting.",
    input_model=GreetInput,
    output_model=GreetOutput,
    handler=greet_handler,
)


# ── ToolSpec ────────────────────────────────────────────────────────

class TestToolSpec:

    def test_input_schema_returns_json_schema(self):
        schema = ADD_TOOL.input_schema()
        assert "properties" in schema
        assert "a" in schema["properties"]
        assert "b" in schema["properties"]

    def test_output_schema_returns_json_schema(self):
        schema = ADD_TOOL.output_schema()
        assert "properties" in schema
        assert "result" in schema["properties"]

    def test_frozen(self):
        with pytest.raises(AttributeError):
            ADD_TOOL.name = "changed"


# ── ToolRegistry ────────────────────────────────────────────────────

class TestToolRegistry:

    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register(ADD_TOOL)
        assert reg.get("add") is ADD_TOOL

    def test_duplicate_registration_raises(self):
        reg = ToolRegistry()
        reg.register(ADD_TOOL)
        with pytest.raises(ValueError, match="already registered"):
            reg.register(ADD_TOOL)

    def test_get_missing_raises_with_available(self):
        reg = ToolRegistry()
        reg.register(ADD_TOOL)
        with pytest.raises(KeyError, match="not found.*add"):
            reg.get("missing")

    def test_list_tools_sorted(self):
        reg = ToolRegistry()
        reg.register(GREET_TOOL)
        reg.register(ADD_TOOL)
        assert reg.list_tools() == ["add", "greet"]

    def test_catalog(self):
        reg = ToolRegistry()
        reg.register(ADD_TOOL)
        cat = reg.catalog()
        assert len(cat) == 1
        assert cat[0]["name"] == "add"
        assert "inputSchema" in cat[0]
        assert "outputSchema" in cat[0]


# ── LocalToolClient ────────────────────────────────────────────────

class TestLocalToolClient:

    @pytest.fixture
    def client(self):
        reg = ToolRegistry()
        reg.register(ADD_TOOL)
        reg.register(GREET_TOOL)
        return LocalToolClient(reg)

    def test_call_add(self, client):
        env = client.call("add", {"a": 3, "b": 4})
        assert isinstance(env, ToolResultEnvelope)
        assert env.payload == {"result": 7}

    def test_call_greet_default(self, client):
        env = client.call("greet", {})
        assert env.payload == {"message": "Hello, world!"}

    def test_call_greet_custom(self, client):
        env = client.call("greet", {"name": "Chris"})
        assert env.payload == {"message": "Hello, Chris!"}

    def test_envelope_meta_tool_name(self, client):
        env = client.call("add", {"a": 1, "b": 2})
        assert env.meta.tool_name == "add"
        assert env.meta.tool_description == "Add two integers."
        assert env.meta.success is True
        assert env.meta.error is None

    def test_envelope_meta_input_args(self, client):
        env = client.call("add", {"a": 5, "b": 10})
        assert env.meta.input_args == {"a": 5, "b": 10}

    def test_envelope_meta_input_hash_deterministic(self, client):
        env1 = client.call("add", {"a": 1, "b": 2})
        env2 = client.call("add", {"a": 1, "b": 2})
        assert env1.meta.input_hash == env2.meta.input_hash
        assert len(env1.meta.input_hash) == 16

    def test_envelope_meta_duration(self, client):
        env = client.call("add", {"a": 1, "b": 2})
        assert env.meta.duration_ms >= 0

    def test_envelope_meta_timestamp(self, client):
        import time
        before = time.time()
        env = client.call("add", {"a": 1, "b": 2})
        after = time.time()
        assert before <= env.meta.timestamp <= after

    def test_envelope_model_dump_flat(self, client):
        env = client.call("add", {"a": 3, "b": 4})
        flat = env.model_dump_flat()
        assert flat["result"] == 7
        assert "_meta" in flat
        assert flat["_meta"]["tool_name"] == "add"

    def test_list_tools_returns_full_defs(self, client):
        tools = client.list_tools()
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "add" in names
        assert "greet" in names
        assert "inputSchema" in tools[0]
        assert "description" in tools[0]

    def test_invalid_input_returns_error_envelope(self, client):
        env = client.call("add", {"a": "not_a_number", "b": 4})
        assert env.is_error is True
        assert env.meta.success is False
        assert env.meta.error == "input_validation_error"
        assert env.structured["kind"] == "input_validation_error"
        assert len(env.content) == 1

    def test_missing_tool_raises_key_error(self, client):
        with pytest.raises(KeyError, match="not found"):
            client.call("nonexistent", {})

    def test_handler_exception_returns_error_envelope(self):
        def bad_handler(inp):
            raise RuntimeError("handler crashed")

        reg = ToolRegistry()
        reg.register(ToolSpec(
            name="bad",
            description="Always fails.",
            input_model=AddInput,
            output_model=AddOutput,
            handler=bad_handler,
        ))
        client = LocalToolClient(reg)

        env = client.call("bad", {"a": 1, "b": 2})
        assert env.is_error is True
        assert env.meta.success is False
        assert env.meta.error == "execution_error"
        assert env.structured["kind"] == "execution_error"

    def test_success_envelope_has_content_and_structured(self, client):
        env = client.call("add", {"a": 3, "b": 4})
        assert env.is_error is False
        assert env.structured == {"result": 7}
        assert len(env.content) == 1
        assert "7" in env.content[0].text
