"""
MCP-Ready, Transport-Agnostic Tool Skeleton
Using Pydantic for schema validation.
"""

from typing import Callable, Type, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel, ValidationError


# ============================================================
# Tool Contract
# ============================================================

@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: Type[BaseModel]
    output_model: Type[BaseModel]
    handler: Callable[[BaseModel], BaseModel]


# ============================================================
# Tool Registry
# ============================================================

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, tool: ToolSpec):
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSpec:
        return self._tools[name]

    def list_tools(self):
        return list(self._tools.keys())


# ============================================================
# Local Tool Client (In-Process Execution)
# ============================================================

class LocalToolClient:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def list_tools(self):
        return self.registry.list_tools()

    def call(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        tool = self.registry.get(tool_name)

        try:
            # Validate input
            validated_input = tool.input_model(**args)

            # Execute handler
            result = tool.handler(validated_input)

            # Validate output
            validated_output = tool.output_model(**result.model_dump())

            return validated_output.model_dump()

        except ValidationError as e:
            return {
                "error": "validation_error",
                "details": e.errors()
            }


# ============================================================
# Example Tools
# ============================================================

class HelloInput(BaseModel):
    name: str = "world"


class HelloOutput(BaseModel):
    message: str


def hello_handler(input_data: HelloInput) -> HelloOutput:
    return HelloOutput(message=f"Hello, {input_data.name}!")


class AddInput(BaseModel):
    a: int
    b: int


class AddOutput(BaseModel):
    result: int


def add_handler(input_data: AddInput) -> AddOutput:
    return AddOutput(result=input_data.a + input_data.b)


# ============================================================
# Wire Everything Together
# ============================================================

if __name__ == "__main__":
    registry = ToolRegistry()

    registry.register(
        ToolSpec(
            name="hello",
            description="Return a friendly greeting.",
            input_model=HelloInput,
            output_model=HelloOutput,
            handler=hello_handler,
        )
    )

    registry.register(
        ToolSpec(
            name="add",
            description="Add two integers.",
            input_model=AddInput,
            output_model=AddOutput,
            handler=add_handler,
        )
    )

    tool_client = LocalToolClient(registry)

    print("Available tools:", tool_client.list_tools())
    print(tool_client.call("hello", {"name": "Chris"}))
    print(tool_client.call("add", {"a": 3, "b": 4}))
