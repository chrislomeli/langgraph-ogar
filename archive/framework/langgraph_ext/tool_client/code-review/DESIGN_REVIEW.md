## What you have that’s strong
1) Tool boundary is clean (input → output)

handler(validated_input) -> output_model is exactly the “pure tool” boundary you want.

2) Registry + schema export is the right direction

ToolSpec.input_schema() and .output_schema() → JSON schema gives you the correct path to MCP inputSchema / outputSchema.

3) Envelope is a good internal observability layer

Putting provenance on the client side is sane. In MCP you’ll still want logging/telemetry/caching, and you don’t want tool handlers caring.

# The main thing to fix (MCP compatibility & realism)
✅ A tool call result in MCP is not “payload dict”

In MCP, a tool returns a CallToolResult with:

content: ContentBlock[] (required)

optional structuredContent

optional isError

Your ToolResultEnvelope.payload is currently just the output model dump, with _meta injected optionally.

That means when you swap to MCP, you’ll have to either:

change downstream logic to accept MCP-style results, or

“fake” MCP into your current shape.

You can avoid future churn by adjusting your envelope now to carry both:

a structured payload (your current dict) and/or

an MCP-style content array

### Minimal change to be future-proof

Keep your internal payload (it’s great for mediators), but also include MCP-ish result fields:

class ToolResultEnvelope(BaseModel):
    meta: ToolResultMeta
    content: list[dict[str, Any]]  # MCP-style blocks (at least one {"type":"text","text":...})
    structured: dict[str, Any] | None = None
    is_error: bool = False


Then your LocalToolClient can set:

structured = validated_output.model_dump()

content = [{"type":"text","text": "<short human-readable summary>"}]

If you don’t want to author summaries, you can default to JSON-in-text:

content = [{"type":"text","text": json.dumps(structured, indent=2, sort_keys=True)}]


This keeps the LLM-facing behavior realistic and keeps your mediator-friendly structured data.

Why this matters: under MCP, the LLM will often “see” the text content; structuredContent is optional and host-dependent. You’ll want your system to work even when only content is used.

# Second big thing: your facade is currently “tool_name + args → envelope”

That’s good — but your tool discovery interface isn’t.

ToolClient.list_tools() returning only names is too thin

To test LLM selection the way MCP does, your harness needs to provide the LLM:

name

description

inputSchema (JSON Schema)

(optional outputSchema)

Right now ToolRegistry.catalog() provides something close, but keys are input_schema not MCP’s inputSchema.

### Make catalog() return MCP-shaped keys

Change:

"input_schema": t.input_schema(),
"output_schema": t.output_schema(),


to:

"inputSchema": t.input_schema(),
"outputSchema": t.output_schema(),


And consider including title (optional) and _meta (optional).

Then upgrade ToolClient:

class ToolClient(ABC):
    def list_tools(self) -> list[dict[str, Any]]: ...


or better, return list[ToolSpecView] (dataclass) that serializes to MCP Tool.

This is the single most important change to support your “LLM must intuit utility” requirement.

# Third thing: exceptions vs tool errors
Your LocalToolClient raises ToolCallError

In MCP practice, tool failures are typically returned as an in-band tool result (isError: true) so the model can correct itself.

You can still raise exceptions for programmer errors, but for validation/execution issues that should be recoverable by the LLM, prefer returning a failed envelope:

return ToolResultEnvelope(
  meta=ToolResultMeta(..., success=False, error="..."),
  is_error=True,
  content=[{"type":"text","text": "..."}],
  structured={"kind":"input_validation_error","details": e.errors()},
)


This will make your local testing behave much more like MCP, because the LLM will be able to see the error and retry.

If you keep raising exceptions, your graph might short-circuit instead of letting the model iterate.

# Fourth thing: you’re doing extra work in output validation

You currently do:

validated_output = tool.output_model.model_validate(result.model_dump())


But result already is AddOutput in your example. That is redundant.

A cleaner pattern:

Let handler return output_model or a dict

Normalize in one place:

try:
    validated_output = tool.output_model.model_validate(result)
except ValidationError as e:
    ...


That way you can implement tools as either “pure Pydantic” or “pure dict” without ceremony.

# Fifth thing: hashing args

Your hash uses default=str, which can cause unstable hashes for objects like datetimes depending on formatting. Two suggestions:

ensure args are JSON-safe before hashing (that’s part of your boundary anyway)

hash the validated input (Pydantic can produce stable JSON)

canonical = validated_input.model_dump_json(sort_keys=True)


Then hash that. Much more deterministic.

# Mediator pattern: good, but one caution

Your mediator routes by tool_name. That’s fine.

Just be aware: if later you combine tools from multiple sources/servers, name collisions become possible. Consider namespacing now:

math.add_numbers

weather.get_forecast

That’s a small change now that prevents pain later.

# If you do just 3 changes, do these

Change tool discovery to return full Tool objects (MCP-shaped: name, description, inputSchema, optional outputSchema).

Return MCP-like tool results: include content[] + optional structured + is_error.

Return errors in-band (envelope with is_error=True) instead of raising for validation/runtime issues.

Those three will make your local harness a very faithful predictor of “what happens under MCP” without bringing JSON-RPC or transport into the picture.

If you want, I’ll rewrite just ToolClient, LocalToolClient, ToolRegistry.catalog(), and the Envelope models in-place (minimal diff, same architecture), keeping your mediator and graph code unchanged except for reading envelope.structured instead of envelope.payload.

lets do that - thank you

Awesome — here’s a minimal-diff rewrite of the four pieces you named (ToolClient, LocalToolClient, ToolRegistry.catalog(), and the envelope models) that:

makes tool discovery MCP-shaped (name/description/inputSchema/outputSchema/...)

makes tool results MCP-shaped (content[], optional structured, is_error)

returns errors in-band (no exceptions for validation/execution errors), so an LLM can self-correct like it would under MCP

keeps your existing mediator pattern basically intact (you’ll just re