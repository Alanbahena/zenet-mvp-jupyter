# Implementation Plan: Subtask 5.2 — Tool Calling Mechanism

## Goal

Replace `_generate_response()` in `BaseAgent` with a multi-turn tool calling loop so agents
can invoke registered tools during a conversation turn. The LLM requests a tool → the agent
executes it → the result is fed back → the LLM continues — repeating until a final text
response is returned.

`run()` is not touched. The boundary designed in 5.1 holds: only `_generate_response()` changes.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `ProviderResponse` dataclass in `core/ai/providers.py` | Retry / backoff logic (5.5) |
| `generate_raw()` on `LlmProvider`, `OpenAiProvider`, `ClaudeProvider` | `AgentRegistry`, `create_agent()` factory (5.5) |
| Claude message format normalization (`_normalize_messages()`) | Live tool-calling tests (5.6) |
| `_generate_response()` replaced with tool loop in `BaseAgent` | Streaming responses |
| `_execute_tool()` — never raises, returns error strings | Multi-agent tool sharing |
| `register_tool()` — auto-creates `ToolRegistry` | Changes to `run()` |
| `_MAX_TOOL_ROUNDS` guard (10 rounds, `ClassVar`) | Changes to `ConversationMemory` |
| 8 new unit tests (all mocked) | Changes to `ToolRegistry` |

---

## The Core Problem

`provider.generate()` returns `str`. When a tool-capable LLM decides to call a function it
does not return text — it returns structured tool call data. The current implementation
discards that entirely: OpenAI coerces `None` content to `""`, Claude returns `""` when no
text block is found.

5.2 solves this by introducing a richer return type (`ProviderResponse`) and a parallel method
(`generate_raw()`) that properly surfaces tool call responses without breaking the existing
`generate()` interface or any 5.1 tests.

---

## Dependencies

| Component | Source | Already exists? |
|-----------|--------|-----------------|
| `LlmProvider`, `OpenAiProvider`, `ClaudeProvider` | `core/ai/providers.py` | Yes |
| `ToolRegistry` | `core/ai/providers.py` | Yes |
| `ConversationMemory` (add_tool_call, add_tool_result) | `core/ai/memory.py` | Yes |
| `BaseAgent`, `_generate_response()` | `core/agents/base_agent.py` | Yes (5.1) |

No new dependencies. No `uv add` required.

---

## Files to Modify

| Action | File |
|--------|------|
| Modify | `core/ai/providers.py` — add `ProviderResponse`; add `generate_raw()` to `LlmProvider`, `OpenAiProvider`, `ClaudeProvider` |
| Modify | `core/agents/base_agent.py` — replace `_generate_response()`; add `_execute_tool()`, `register_tool()`, `_MAX_TOOL_ROUNDS` |
| Modify | `tests/unit/test_agents.py` — add `_MockToolProvider` fixture and 8 new tests |

No new files. No changes to `core/__init__.py` — `ProviderResponse` is internal to the
provider layer and is not a public export.

---

## Implementation Steps

### Step 1: Add `ProviderResponse` to `core/ai/providers.py`

Add before `class LlmProvider`. This is the return type of `generate_raw()`.

```python
@dataclass
class ProviderResponse:
    """
    Rich response from provider.generate_raw().

    Exactly one of text or tool_calls will be set per response:
        - text:       set when the LLM returns a final text answer
        - tool_calls: set when the LLM requests one or more tool executions

    tool_calls format (normalized, provider-agnostic):
        [
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "arguments": '{"key": "value"}'   # JSON string, always
                }
            },
            ...
        ]

    arguments is always a JSON string (not a dict). This matches OpenAI's native
    format and ensures round-trip consistency when messages are sent back to the API.
    Claude's input dict is serialized to JSON when building ProviderResponse.
    _execute_tool() handles JSON parsing before calling ToolRegistry.execute().
    """

    text: str | None = None
    tool_calls: list[dict[str, Any]] | None = None

    @property
    def has_tool_calls(self) -> bool:
        """True when the LLM returned tool call requests instead of text."""
        return bool(self.tool_calls)
```

**Why `arguments` is always a JSON string:**

OpenAI returns `arguments` as a JSON string. Claude returns `input` as a dict. The
normalized format uses JSON string throughout because:

1. OpenAI API requires `arguments` as a JSON string when messages are sent back in the
   next turn. Storing as dict would require re-serialization in `_normalize_messages()`.
2. `ConversationMemory.add_tool_call()` stores exactly what it receives. Keeping one
   format (string) means the stored messages are always valid for OpenAI without
   transformation.
3. `_execute_tool()` already handles `isinstance(args, str)` → `json.loads()`, so the
   parsing cost is paid once, at execution time.

---

### Step 2: Add `generate_raw()` to `LlmProvider`

Add after the existing `generate()` method. This is a **concrete default** (not abstract)
to preserve backward compatibility with any custom provider subclasses.

```python
def generate_raw(
    self,
    *,
    prompt: str | None = None,
    system: str | None = None,
    tools: ToolRegistry | None = None,
    structured_output: bool = False,
    messages: list | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> ProviderResponse:
    """
    Generate a response and return a ProviderResponse (text or tool calls).

    This method differs from generate() in two ways:
        1. tools accepts ToolRegistry | None instead of list | None.
           Each provider calls .to_openai_tools() or .to_anthropic_tools() internally.
        2. Returns ProviderResponse instead of str, surfacing tool call data
           that generate() discards.

    Default implementation: wraps generate() with tools=None (text-only fallback).
    Providers that support tool calling MUST override this method.

    Note: The default passes tools=None to generate() because the types are
    incompatible (ToolRegistry vs list). A provider using the default will silently
    ignore any registered tools. This is intentional — it allows the framework to
    degrade gracefully with providers that do not implement tool support.
    """
    self._validate_input(prompt, messages)
    text = self._do_generate(
        prompt=prompt,
        system=system,
        tools=None,          # ToolRegistry cannot be passed to list-typed generate()
        structured_output=structured_output,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return ProviderResponse(text=text)
```

**Important:** The default passes `tools=None` to `_do_generate()`. This is intentional.
A provider that does not override `generate_raw()` will silently ignore tool registration.
Document this clearly so debugging is straightforward: if tools appear to not be called,
check that the provider overrides `generate_raw()`.

---

### Step 3: `OpenAiProvider.generate_raw()`

```python
def generate_raw(
    self,
    *,
    prompt: str | None = None,
    system: str | None = None,
    tools: ToolRegistry | None = None,
    structured_output: bool = False,
    messages: list | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> ProviderResponse:
    """
    Generate with tool calling support.

    When tools are provided and the LLM returns tool calls:
        - Normalizes to provider-agnostic format
        - arguments is kept as JSON string (OpenAI native format, no conversion)

    When the LLM returns text (no tool calls): returns ProviderResponse(text=...).
    """
    self._validate_input(prompt, messages)

    if messages is not None:
        api_messages: list[dict] = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)
    else:
        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.append({"role": "user", "content": prompt or ""})

    kwargs: dict = {
        "model": self.model_name,
        "messages": api_messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if tools:
        kwargs["tools"] = tools.to_openai_tools()
    if structured_output:
        kwargs["response_format"] = {"type": "json_object"}

    response = self.client.chat.completions.create(**kwargs)
    msg = response.choices[0].message

    if msg.tool_calls:
        normalized = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,  # already a JSON string
                },
            }
            for tc in msg.tool_calls
        ]
        return ProviderResponse(tool_calls=normalized)

    return ProviderResponse(text=msg.content if msg.content is not None else "")
```

---

### Step 4: `ClaudeProvider._normalize_messages()` and `generate_raw()`

Claude uses a different message format for tool interactions. Two conversions are needed:

**Incoming messages (OpenAI format → Claude format):**

| OpenAI format (stored in memory) | Claude format (sent to API) |
|----------------------------------|------------------------------|
| `{"role": "assistant", "content": null, "tool_calls": [...]}` | `{"role": "assistant", "content": [{"type": "tool_use", "id": "...", "name": "...", "input": {...}}]}` |
| `{"role": "tool", "tool_call_id": "x", "content": "..."}` | `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "..."}]}` |

**Critical Claude API requirement — consecutive tool results must be merged:**

When an LLM calls multiple tools in one turn, the agent executes them sequentially and
stores multiple `{"role": "tool"}` messages. OpenAI accepts these as separate messages.
Claude does not — it requires all tool results from a single turn to be merged into one
`user` message with multiple `tool_result` content blocks:

```python
# What memory stores after two tool calls (two separate messages):
{"role": "tool", "tool_call_id": "x", "content": "result 1"}
{"role": "tool", "tool_call_id": "y", "content": "result 2"}

# What Claude API requires (one user message, both results combined):
{
    "role": "user",
    "content": [
        {"type": "tool_result", "tool_use_id": "x", "content": "result 1"},
        {"type": "tool_result", "tool_use_id": "y", "content": "result 2"},
    ]
}
```

`_normalize_messages()` implements this by scanning the message list and grouping all
consecutive `tool` role messages into a single Claude `user` message.

```python
def _normalize_messages(self, messages: list[dict]) -> list[dict]:
    """
    Convert OpenAI-format messages to Claude API format.

    Handles:
        1. Filters system role messages (Claude uses system= parameter instead)
        2. Converts assistant tool_calls messages to Claude tool_use format
        3. Converts tool role messages to Claude tool_result format
        4. Merges consecutive tool role messages into a single user message
           (Claude API requirement: all results from one turn = one user message)
    """
    result: list[dict] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role")

        if role == "system":
            i += 1
            continue

        if role == "assistant" and msg.get("tool_calls"):
            # Convert OpenAI tool_calls format to Claude tool_use blocks
            content_blocks = []
            for tc in msg["tool_calls"]:
                args = tc["function"]["arguments"]
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                content_blocks.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["function"]["name"],
                    "input": args,
                })
            result.append({"role": "assistant", "content": content_blocks})
            i += 1
            continue

        if role == "tool":
            # Collect all consecutive tool messages and merge into one user message
            tool_result_blocks = []
            while i < len(messages) and messages[i].get("role") == "tool":
                t = messages[i]
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": t["tool_call_id"],
                    "content": t["content"],
                })
                i += 1
            result.append({"role": "user", "content": tool_result_blocks})
            continue

        result.append(msg)
        i += 1

    return result


def generate_raw(
    self,
    *,
    prompt: str | None = None,
    system: str | None = None,
    tools: ToolRegistry | None = None,
    structured_output: bool = False,
    messages: list | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> ProviderResponse:
    """
    Generate with tool calling support for Anthropic Claude.

    Normalizes incoming messages to Claude format before the API call.
    Detects tool_use blocks in response and normalizes to provider-agnostic format.
    arguments in the returned ProviderResponse is always a JSON string.
    """
    self._validate_input(prompt, messages)

    if messages is not None:
        api_messages = self._normalize_messages(messages)
    else:
        api_messages = [{"role": "user", "content": prompt or ""}]

    effective_system = system or ""
    if structured_output:
        json_instruction = " Respond with valid JSON only. Do not include markdown code fences."
        effective_system = (
            (effective_system + json_instruction).strip()
            if effective_system
            else "Respond with valid JSON only. Do not include markdown code fences."
        )

    kwargs: dict = {
        "model": self.model_name,
        "max_tokens": max_tokens,
        "messages": api_messages,
        "temperature": temperature,
    }
    if effective_system:
        kwargs["system"] = effective_system
    if tools:
        kwargs["tools"] = tools.to_anthropic_tools()

    response = self.client.messages.create(**kwargs)

    tool_use_blocks = [b for b in response.content if getattr(b, "type", None) == "tool_use"]
    if tool_use_blocks:
        normalized = [
            {
                "id": b.id,
                "type": "function",
                "function": {
                    "name": b.name,
                    "arguments": json.dumps(b.input),  # dict → JSON string
                },
            }
            for b in tool_use_blocks
        ]
        return ProviderResponse(tool_calls=normalized)

    for block in response.content:
        text = getattr(block, "text", None)
        if text:
            return ProviderResponse(text=text)
    return ProviderResponse(text="")
```

**Note on `json` import:** `ClaudeProvider._normalize_messages()` and `generate_raw()` use
`json.loads()` / `json.dumps()`. `import json` must be added to `providers.py` (it is not
currently imported there — used in `utils.py` only).

---

### Step 5: Replace `_generate_response()` in `base_agent.py`

Add `_MAX_TOOL_ROUNDS` as a `ClassVar` alongside the schema ClassVars. Replace the
single-turn `_generate_response()` from 5.1 with the tool loop.

```python
_MAX_TOOL_ROUNDS: ClassVar[int] = 10
```

```python
def _generate_response(self, system_prompt: str) -> str:
    """
    Generate LLM response using current conversation memory.

    When self.tools is None: single-turn call (identical to 5.1 behavior).
    When self.tools is set: multi-turn tool loop.

    Tool loop (per round):
        1. Call provider.generate_raw() with tools and current memory
        2. If tool calls returned: execute each, add results to memory, repeat
        3. If text returned: return it (loop exits)
        4. After _MAX_TOOL_ROUNDS without a text response: raise RuntimeError

    Automatically enables structured output mode when RESPONSE_MODEL is defined,
    consistent with the 5.1 behavior for the no-tools path.

    Note: prompt=None is critical. The user message is already in self.memory.
    Passing prompt alongside messages would duplicate it in the conversation.

    Subtask 5.3 does not change this method.
    Subtask 5.5 wraps the provider call with retry logic.
    """
    for _ in range(self._MAX_TOOL_ROUNDS):
        if self.tools is not None:
            raw = self.provider.generate_raw(
                prompt=None,
                system=system_prompt,
                messages=self.memory.get_messages(),
                tools=self.tools,
                structured_output=self.RESPONSE_MODEL is not None,
            )
            if raw.has_tool_calls:
                self.memory.add_tool_call(raw.tool_calls)
                for call in raw.tool_calls:
                    result = self._execute_tool(call)
                    self.memory.add_tool_result(call["id"], result)
                continue
            return raw.text or ""
        else:
            # No tools — single-turn (5.1 behavior preserved exactly)
            return self.provider.generate(
                prompt=None,
                system=system_prompt,
                messages=self.memory.get_messages(),
                structured_output=self.RESPONSE_MODEL is not None,
            )

    raise RuntimeError(
        f"[{self.name}] Exceeded maximum tool rounds ({self._MAX_TOOL_ROUNDS}). "
        "The LLM did not return a final text response within the allowed rounds."
    )
```

**Design notes:**

- **No-tools path is identical to 5.1.** `provider.generate()` is called directly. All
  21 existing tests continue to pass without modification.

- **`_MAX_TOOL_ROUNDS` is a `ClassVar`.** Concrete agents can override it at the class
  level if a specific workflow legitimately requires more rounds. The guard prevents
  infinite loops caused by a misbehaving LLM or circular tool dependencies.

- **`raw.text or ""`:** handles the case where `ProviderResponse.text` is `None` (should
  not happen with correct provider implementations, but defensive). An empty string `""`
  is returned without error — retry/empty-response handling is added in 5.5.

---

### Step 6: Add `_execute_tool()` to `base_agent.py`

Add `import json` to `base_agent.py` imports (currently not imported).

```python
def _execute_tool(self, tool_call: dict[str, Any]) -> str:
    """
    Execute a single tool call and return the result as a string.

    Never raises. Tool errors are returned as descriptive strings so the LLM
    can read them, explain the issue to the user, or try a different approach.

    Args:
        tool_call: Normalized tool call dict from ProviderResponse.tool_calls.
                   Format: {"id": "...", "function": {"name": "...", "arguments": "..."}}
                   arguments is a JSON string; this method parses it before execution.

    Returns:
        str(result) on success.
        "Error: tool '<name>' not registered." if tool is unknown.
        "Error executing '<name>': <exception>" if tool raises during execution.
    """
    function = tool_call.get("function", {})
    name = function.get("name", "")
    args = function.get("arguments", {})

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {}

    try:
        result = self.tools.execute(name, args)
        return str(result)
    except ValueError:
        return f"Error: tool '{name}' not registered."
    except Exception as e:
        return f"Error executing '{name}': {e}"
```

---

### Step 7: Add `register_tool()` to `base_agent.py`

Add `from collections.abc import Callable` to `base_agent.py` imports.

```python
def register_tool(
    self,
    name: str,
    func: Callable[..., Any],
    *,
    description: str,
    parameters_schema: dict[str, Any] | None = None,
) -> None:
    """
    Register a tool with the agent.

    Auto-creates a ToolRegistry if the agent was initialized without one (tools=None).
    Subsequent calls reuse the same registry.

    Args:
        name:              Tool name (must be unique; duplicates overwrite).
        func:              Callable to execute when the LLM requests this tool.
        description:       Human/LLM-readable description of what the tool does.
        parameters_schema: JSON schema dict for the tool's parameters.
                           If None, defaults to {"type": "object", "properties": {}}.

    Example:
        agent.register_tool(
            "get_inventory_item",
            lambda name: registry.get_by_name(name),
            description="Look up an inventory item by name.",
            parameters_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )
    """
    if self.tools is None:
        self.tools = ToolRegistry()
    self.tools.register(
        name, func, description=description, parameters_schema=parameters_schema
    )
```

---

### Step 8: New imports in `base_agent.py`

Two imports to add:

```python
import json
from collections.abc import Callable
```

---

## Test Strategy

### New fixture: `_MockToolProvider`

The existing `_MockProvider` (from 5.1) inherits the default `generate_raw()` from
`LlmProvider`, which wraps `_do_generate()` and always returns `ProviderResponse(text=...)`.
That is correct and sufficient for the no-tools path.

For tool calling tests, we need a provider that can return `ProviderResponse(tool_calls=...)`
on configured calls:

```python
class _MockToolProvider(LlmProvider):
    """
    Provider that returns a pre-configured sequence of ProviderResponse objects.

    Used to simulate multi-turn tool interactions without any API calls.
    Raises StopIteration if more calls are made than responses configured.
    """

    def __init__(self, responses: list[ProviderResponse]) -> None:
        super().__init__(model_name="mock-tool")
        self._responses = iter(responses)
        self.call_count = 0

    def _do_generate(self, **kwargs) -> str:
        # Not used in tool calling tests — generate_raw() is called instead
        return ""

    def generate_raw(self, **kwargs) -> ProviderResponse:
        self.call_count += 1
        return next(self._responses)
```

### 8 new tests

| # | Test | Verifies |
|---|------|----------|
| 1 | `register_tool()` with `tools=None` creates a `ToolRegistry` | Auto-create on first call |
| 2 | `register_tool()` reuses existing `ToolRegistry` when already set | No double-creation |
| 3 | `_execute_tool()` returns correct string for valid registered tool | Happy path |
| 4 | `_execute_tool()` returns error string for unregistered tool (no exception) | Error isolation |
| 5 | `_execute_tool()` returns error string when tool function raises (no exception) | Error isolation |
| 6 | Multi-turn: provider returns tool call on turn 1, text on turn 2 → text returned from `run()` | Full loop |
| 7 | Memory has tool call message + tool result message after one tool-use turn | Memory population |
| 8 | `_generate_response()` raises `RuntimeError` after `_MAX_TOOL_ROUNDS` tool responses with no text | Infinite loop guard |

**Test 6 detail:**

```python
responses = [
    ProviderResponse(tool_calls=[{
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_value", "arguments": '{"key": "x"}'},
    }]),
    ProviderResponse(text='{"reply": "done"}'),
]
provider = _MockToolProvider(responses)
agent.register_tool("get_value", lambda key: "42", description="Get value by key.")
result = agent.run(input_data={"message": "hi"})
assert result == {"reply": '{"reply": "done"}'}
assert provider.call_count == 2
```

**Test 7 detail:** After test 6 run, assert:
- `memory.get_messages()` contains a message with `role == "assistant"` and `tool_calls` key
- `memory.get_messages()` contains a message with `role == "tool"` and `content == "42"`

**Test 8 detail:**

```python
# Provider always returns tool calls, never text
responses = [
    ProviderResponse(tool_calls=[{
        "id": f"call_{i}", "type": "function",
        "function": {"name": "loop_tool", "arguments": "{}"},
    }])
    for i in range(BaseAgent._MAX_TOOL_ROUNDS + 1)
]
provider = _MockToolProvider(responses)
agent.register_tool("loop_tool", lambda: "ok", description="Loops forever.")
with self.assertRaises(RuntimeError) as ctx:
    agent.run(input_data={"message": "hi"})
assert str(BaseAgent._MAX_TOOL_ROUNDS) in str(ctx.exception)
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `tools=None`, LLM returns text | Single-turn path; `generate()` called; no tool loop |
| `tools` set, LLM returns text immediately (no tool calls) | Loop exits after 1 round |
| `tools` set, LLM requests unknown tool | `_execute_tool()` returns error string; LLM continues |
| `tools` set, tool function raises | `_execute_tool()` returns error string; LLM continues |
| `tools` set, LLM requests multiple tools in one turn | All executed sequentially; all results stored before next round |
| `arguments` is a malformed JSON string | `json.loads()` fails; `args = {}`; tool called with no arguments |
| `raw.text` is empty string `""` | Returned as-is; empty response handling deferred to 5.5 |
| `_MAX_TOOL_ROUNDS` exceeded | `RuntimeError` raised with agent name and round limit in message |
| Provider does not override `generate_raw()` | Default wraps `generate()`; tools silently ignored; text returned |
| `ClaudeProvider` receives 3 consecutive tool result messages | `_normalize_messages()` merges all into one user message |
| `ClaudeProvider` receives tool call with dict arguments | Serialized to JSON string via `json.dumps()` before returning in `ProviderResponse` |

---

## Deliverable Checklist

### `core/ai/providers.py`
- [ ] `import json` added
- [ ] `ProviderResponse` dataclass added (before `LlmProvider`)
- [ ] `ProviderResponse.has_tool_calls` property
- [ ] `LlmProvider.generate_raw()` default implementation (wraps `_do_generate`, passes `tools=None`)
- [ ] `OpenAiProvider.generate_raw()` — detects `msg.tool_calls`, normalizes to common format
- [ ] `ClaudeProvider._normalize_messages()` — converts OpenAI format → Claude format, merges consecutive tool results
- [ ] `ClaudeProvider.generate_raw()` — calls `_normalize_messages`, detects `tool_use` blocks, serializes `input` dict → JSON string

### `core/agents/base_agent.py`
- [ ] `import json` added
- [ ] `from collections.abc import Callable` added
- [ ] `_MAX_TOOL_ROUNDS: ClassVar[int] = 10` added alongside schema ClassVars
- [ ] `_generate_response()` replaced with tool loop
- [ ] No-tools path calls `provider.generate()` (identical to 5.1)
- [ ] Tool path calls `provider.generate_raw()` with `tools=self.tools`
- [ ] `_execute_tool()` added — never raises, returns error strings
- [ ] `register_tool()` added — auto-creates `ToolRegistry`, keyword-only `description` and `parameters_schema`

### Tests
- [ ] `_MockToolProvider` fixture added to `tests/unit/test_agents.py`
- [ ] `from core.ai.providers import ProviderResponse` import added to test file
- [ ] 8 new tests implemented and passing
- [ ] All 8 pass: `python -m pytest tests/unit/test_agents.py -v -k Tool`
- [ ] All 21 prior tests still pass (no-tools path unchanged)
- [ ] Full suite still passes: `python -m pytest tests/unit/ -k "not Live" -v`

---

## Notes

- **`generate()` is untouched.** All 5.1 tests pass without modification. The no-tools path
  in `_generate_response()` still calls `provider.generate()` directly.

- **`ProviderResponse` is internal.** It is not exported from `core/__init__.py`. Only
  `providers.py` and `test_agents.py` (for mock setup) reference it directly.

- **`_MAX_TOOL_ROUNDS` as `ClassVar`:** Concrete agents in Tasks 7–12 can override it at
  the class level if needed. Default of 10 is conservative — most tool interactions resolve
  in 1–3 rounds.

- **`run()` is not changed.** The boundary from 5.1 holds: `run()` calls
  `_generate_response()`; all tool logic is inside `_generate_response()`.

- **`json` import in `providers.py`:** Currently `json` is only imported in `utils.py`. The
  `ClaudeProvider` modifications require it for `json.loads()` / `json.dumps()` in
  `_normalize_messages()` and `generate_raw()`.

- **Subtask 5.3** adds `_data_store` to `BaseAgent` and extends `save_state()`/`load_state()`
  to persist it. `_generate_response()` is not changed again until 5.5 (retry logic).

- **Live tool calling tests** are out of scope for 5.2. They belong in 5.6 alongside other
  live integration tests.
