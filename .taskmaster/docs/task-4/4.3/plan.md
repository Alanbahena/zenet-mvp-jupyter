# Implementation plan: Subtask 4.3 — ToolRegistry

## Goal

Implement `ToolRegistry`: a provider-agnostic registry for LLM tools (function calling). It stores tool name, callable, description, and optional JSON Schema for parameters; exposes `to_openai_tools()` and `to_anthropic_tools()` for use with existing providers; and provides `execute(name, arguments)` to run a registered function when the model returns a tool call.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `ToolRegistry` in `core/llm_framework.py` | Dedicated `core/tool_registry.py` (unless file grows too large) |
| `register(name, func, description, parameters_schema=None)` | Automatic schema inference from function signature (`infer_schema`) |
| `to_openai_tools()` and `to_anthropic_tools()` | Tool call parsing from provider response (Task 5 agent loop) |
| `execute(name, arguments) -> Any` | Tool result formatting back into assistant message |
| JSON Schema for parameters (explicit dict) | External `jsonschema` validation of arguments before execute |

---

## Dependencies

- **Task 4.1** — LlmProvider, OpenAiProvider (done)
- **Task 4.2** — ClaudeProvider (done); both providers accept `tools` list
- **External:** None (no new dependencies)
- **API keys:** Not required for ToolRegistry itself

---

## Files to Modify / Create

- `core/llm_framework.py` — add `ToolRegistry` class
- `core/__init__.py` — export `ToolRegistry`
- `tests/unit/test_llm_framework.py` — add tests for ToolRegistry

---

## Tool format comparison

| Aspect | OpenAI | Anthropic |
|--------|--------|-----------|
| Wrapper | `{"type": "function", "function": {...}}` | Top-level object, no wrapper |
| Name | `function.name` | `name` |
| Description | `function.description` | `description` |
| Parameters | `function.parameters` (JSON Schema) | `input_schema` (JSON Schema) |

Internal representation (per tool): `name`, `description`, `parameters_schema` (dict). Default when `parameters_schema` is `None`: `{"type": "object", "properties": {}}`.

---

## Breakdown

### 1. Internal storage

- Use a **dict** to store entries: `dict[str, _ToolEntry]` for O(1) lookup in `execute()`.
- Python 3.7+ dicts preserve insertion order, so registration order is guaranteed.
- Define a private dataclass for type safety:

```python
@dataclass
class _ToolEntry:
    name: str
    func: Callable[..., Any]
    description: str
    parameters_schema: dict[str, Any] | None
```

- **Naming:** Duplicate `name` registration overwrites (last wins) so tests and notebooks can re-register without clearing.
- Type hints: `from collections.abc import Callable`, `from typing import Any`, `from dataclasses import dataclass`.

---

### 2. `register(name, func, description, parameters_schema=None) -> None`

```python
def register(
    self,
    name: str,
    func: Callable[..., Any],
    description: str,
    parameters_schema: dict[str, Any] | None = None
) -> None:
```

- Create and store a `_ToolEntry` with the four fields in the internal dict: `self._tools[name] = _ToolEntry(...)`.
- If `parameters_schema` is `None`, store `None`; when exporting to OpenAI/Anthropic, use `{"type": "object", "properties": {}}`.
- No validation of `parameters_schema` structure in MVP (caller provides valid JSON Schema).
- **Validation (required):** Raise `ValueError` if `name.strip() == ""` or `description.strip() == ""` to catch bugs early.

---

### 3. `to_openai_tools() -> list[dict[str, Any]]`

```python
def to_openai_tools(self) -> list[dict[str, Any]]:
```

- Return a list of OpenAI tool definitions.
- For each registered tool in `self._tools.values()`:
  - `{"type": "function", "function": {"name": name, "description": description, "parameters": parameters_schema or {"type": "object", "properties": {}}}}`.
- Order: preserves registration order (dict insertion order guaranteed in Python 3.7+).

---

### 4. `to_anthropic_tools() -> list[dict[str, Any]]`

```python
def to_anthropic_tools(self) -> list[dict[str, Any]]:
```

- Return a list of Anthropic tool definitions.
- For each registered tool in `self._tools.values()`:
  - `{"name": name, "description": description, "input_schema": parameters_schema or {"type": "object", "properties": {}}}`.
- Same order as `to_openai_tools()` (preserves registration order).

---

### 5. `execute(name: str, arguments: dict | None = None) -> Any`

```python
def execute(self, name: str, arguments: dict | None = None) -> Any:
```

- Default `arguments` to `{}` if `None`: `arguments = arguments or {}`.
- Look up the registered function by `name` in `self._tools`.
- If not found: raise `ValueError` with message `f"Unknown tool: {name}"`.
- Call the function with the arguments using `**arguments` (kwargs): `return self._tools[name].func(**arguments)`.
- **Rationale:** Caller (agent loop) is responsible for passing the dict returned by the LLM (e.g. from JSON). If the LLM returns extra keys, the function may raise `TypeError`; that is acceptable for MVP.
- Return value: whatever the function returns (could be str, dict, etc.); no wrapping.

---

### 6. Optional: list / get names

- Optional for MVP: `def names(self) -> list[str]` or `def get(name) -> ...` for introspection. Not required by Task 4 master plan; add only if tests or docs benefit.

---

### 7. Exports and docstring

- Add `ToolRegistry` to `core/__init__.py` (import and `__all__`).
- Update `core/llm_framework.py` module docstring to mention ToolRegistry.

---

## Edge cases

| Case | Behavior |
|------|----------|
| `register(name="", ...)` or empty description | Raise `ValueError` (validation required) |
| `parameters_schema is None` | Use `{"type": "object", "properties": {}}` in both OpenAI and Anthropic output |
| `execute(name, None)` or missing arguments | Default to `{}` (empty dict) |
| `execute(name, ...)` with unknown `name` | Raise `ValueError` with message `f"Unknown tool: {name}"` |
| `execute(name, arguments)` when `func(**arguments)` raises | Let exception propagate (e.g. `TypeError`, `KeyError`) |
| Empty registry | `to_openai_tools()` and `to_anthropic_tools()` return `[]` |
| Duplicate `register(name, ...)` | Overwrite previous registration (last wins) |
| `arguments` with keys that func does not accept | `func(**arguments)` may raise `TypeError` — acceptable in MVP |

---

## Test strategy

Unit tests (no API calls):

1. **register and to_openai_tools:** Register one tool with description and optional `parameters_schema`; call `to_openai_tools()`; assert list length 1, structure `type`/`function`/`name`/`description`/`parameters`.
2. **to_openai_tools default schema:** Register with `parameters_schema=None`; assert `parameters` is `{"type": "object", "properties": {}}`.
3. **to_anthropic_tools:** Same tool; call `to_anthropic_tools()`; assert `name`, `description`, `input_schema` (no `type: "function"` wrapper).
4. **execute:** Register a callable that returns a value; `execute(name, {"key": "value"})` returns that value; assert callable was called with expected kwargs.
5. **execute with None arguments:** `execute(name, None)` defaults to `{}` and calls function with no args.
6. **execute unknown name:** `execute("nonexistent", {})` raises `ValueError` with "Unknown tool" message.
7. **register validation:** `register(name="", ...)` or `register(..., description="")` raises `ValueError`.
8. **Multiple tools:** Register two tools; `to_openai_tools()` and `to_anthropic_tools()` return length 2; order preserved.
9. **Duplicate register:** Register same name twice with different func; second overwrites; `execute` calls the second function.

Optional: integration test with a provider (e.g. `OpenAiProvider().generate(..., tools=registry.to_openai_tools())`) to ensure format is accepted; can be covered in 4.7 or later.

---

## Deliverable checklist

- [x] Define `_ToolEntry` dataclass in `core/llm_framework.py`
- [x] Implement `ToolRegistry` in `core/llm_framework.py` with dict storage: `dict[str, _ToolEntry]`
- [x] Implement `register()` with validation: raise `ValueError` for empty name/description
- [x] Implement `to_openai_tools()` and `to_anthropic_tools()` with proper type hints
- [x] Implement `execute()` with `arguments: dict | None = None` defaulting to `{}`
- [x] Raise `ValueError` for unknown tool names in `execute()`
- [x] Default `parameters_schema` to `{"type": "object", "properties": {}}` when exporting
- [x] Add `ToolRegistry` to `core/__init__.py` exports
- [x] Add unit tests in `tests/unit/test_llm_framework.py` for ToolRegistry (all 9 test cases)
- [x] Run `python -m pytest tests/unit/test_llm_framework.py -v`

---

## Notes

- **Storage structure:** Use `dict[str, _ToolEntry]` for O(1) lookup and guaranteed insertion order (Python 3.7+).
- **Error handling:** Use `ValueError` consistently for validation errors (empty name/description, unknown tool).
- **No infer_schema:** Callers must pass `parameters_schema` explicitly. Inferring from `inspect.signature` or similar is out of scope for MVP.
- **JSON Schema:** We do not validate that `parameters_schema` is valid JSON Schema; we pass it through to the APIs. Invalid schema may cause provider errors at call time.
- **execute and agent loop:** Task 5 will consume tool_calls from the provider response and call `registry.execute(tool_name, arguments)`; ToolRegistry does not parse provider responses.
- **File location:** Start in `core/llm_framework.py`. If the file becomes too large, extract to `core/tool_registry.py` and re-export from `llm_framework` or `__init__.py`.
