# Implementation plan: Task 4 — LLM integration framework

## Goal

Create a framework for integrating LLMs (OpenAI, Claude) with structured outputs, function calling, and tool use. The framework provides a unified `LlmProvider` interface, concrete providers for OpenAI and Anthropic, prompt utilities, a tool registry, structured output parsing, and conversation memory.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `LlmProvider` base class with `generate(prompt, tools, structured_output)` | Streaming responses (deferred) |
| `OpenAiProvider` and `ClaudeProvider` | Custom fine-tuned or self-hosted models |
| `core/prompts.py` — prompt templates and utilities | Embeddings or vector search |
| `ToolRegistry` for function calling / tool use | Multi-turn agent orchestration (Task 5) |
| Structured output parsing and JSON validation | Rate limiting, retries, backoff (MVP: minimal) |
| Conversation memory system | Persistent memory across sessions |

---

## Dependencies

- **Task 1** — Project setup (done)
- **External:** `openai>=2.20.0` (already in pyproject.toml), `anthropic` (to add)

---

## Model defaults (CLAUDE.md)

| Provider | Default model |
|----------|---------------|
| OpenAI | `gpt-4` (or latest stable) |
| Claude | `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5-20251001` |

---

## Breakdown

### Phase 4.1 — Provider base and OpenAI

**Files:** `core/llm_framework.py`

- Define `LlmProvider` abstract base class:
  - `__init__(self, model_name: str)`
  - `generate(self, prompt: str, *, tools: list | None = None, structured_output: type | None = None, messages: list | None = None) -> str`
  - All providers accept a string `prompt` or a `messages` list (for multi-turn)
- Implement `OpenAiProvider`:
  - Uses `openai.OpenAI()` (reads `OPENAI_API_KEY` from env)
  - Maps `tools` to OpenAI tools format
  - Maps `structured_output` to `response_format={"type": "json_object"}` when set
  - Returns `response.choices[0].message.content`

**Design choice:** `generate` returns a plain string. Structured output parsing is separate (Phase 4.4).

---

### Phase 4.2 — Claude provider

**Files:** `core/llm_framework.py`

- Add `anthropic` to `pyproject.toml`: `uv add anthropic`
- Implement `ClaudeProvider`:
  - Uses `anthropic.Anthropic()` (reads `ANTHROPIC_API_KEY` from env)
  - Maps `tools` to Anthropic tool format (slightly different from OpenAI)
  - Supports `structured_output` via constrained output / JSON mode where available
  - Returns `message.content[0].text`

**Note:** Claude tool format differs from OpenAI. Abstract tool definitions in a provider-agnostic form and convert per provider.

---

### Phase 4.3 — ToolRegistry

**Files:** `core/llm_framework.py` (or `core/tool_registry.py` if it grows)

- `ToolRegistry` class:
  - `register(name: str, func: Callable, description: str, parameters_schema: dict | None = None) -> None`
  - `to_openai_tools() -> list` — returns OpenAI tools format
  - `to_anthropic_tools() -> list` — returns Anthropic tools format
  - `execute(name: str, arguments: dict) -> Any` — invokes the registered function
- Tool schema: use JSON Schema for parameters; `parameters_schema` can be inferred from `func` signature or provided explicitly
- Keep schema generation simple: optional `infer_schema(func)` helper for basic types

---

### Phase 4.4 — Structured output parsing and validation

**Files:** `core/llm_framework.py` or `core/llm_utils.py`

- `parse_structured_output(raw: str, schema: type | dict) -> Any`:
  - Parse JSON from raw string (handle markdown code blocks like ```json ... ```)
  - If `schema` is a `dict` (JSON Schema): validate and return parsed dict
  - If `schema` is a dataclass type: validate keys and construct instance (or return dict for simplicity)
- Handle parse errors: raise `ValueError` with clear message
- Optional: `validate_json_schema(data: dict, schema: dict) -> bool` using `jsonschema` if needed (or manual validation for MVP)

---

### Phase 4.5 — Prompt utilities

**Files:** `core/prompts.py`

- `PromptTemplate` or simple functions:
  - `format_system_prompt(role: str, context: str | None = None) -> str`
  - `format_user_prompt(template: str, **kwargs) -> str` — simple `str.format` wrapper
- Restaurant/recipe-specific prompt fragments (if needed for later notebooks):
  - e.g. `INGREDIENT_EXTRACTION_PROMPT`, `RECIPE_ANALYSIS_PROMPT` (stubs or minimal)
- No over-engineering: start with plain functions, not a templating engine

---

### Phase 4.6 — Conversation memory

**Files:** `core/llm_framework.py` or `core/memory.py`

- `ConversationMemory` class:
  - `add_user(message: str) -> None`
  - `add_assistant(message: str) -> None`
  - `get_messages() -> list[dict]` — returns `[{"role": "user", "content": "..."}, ...]`
  - `clear() -> None`
  - Optional: `truncate(max_tokens: int | None)` — trim oldest messages (deferred if complex)
- In-memory only (no persistence in MVP)
- `LlmProvider.generate` accepts optional `messages`; if provided, use instead of single `prompt`

---

### Phase 4.7 — Exports and tests

**Files:** `core/__init__.py`, `tests/unit/test_llm_framework.py`

- Export from `core/__init__.py`:
  - `LlmProvider`, `OpenAiProvider`, `ClaudeProvider`
  - `ToolRegistry`, `ConversationMemory`
  - From `core/prompts`: main helpers
- Unit tests (with mocked API calls):
  - Provider interface: `OpenAiProvider` and `ClaudeProvider` return string from `generate` (mock `client.chat.completions.create` / `anthropic.messages.create`)
  - ToolRegistry: register, execute, format conversion
  - Structured output: parse JSON, handle code blocks, raise on invalid
  - ConversationMemory: add, get, clear
- Integration-style test (optional, skipped if no API key): one real call per provider to verify connectivity

---

## File layout

```
core/
├── llm_framework.py   # LlmProvider, OpenAiProvider, ClaudeProvider, ToolRegistry, ConversationMemory
├── prompts.py         # Prompt utilities
└── __init__.py        # Updated exports

tests/
└── unit/
    └── test_llm_framework.py
```

---

## API design (summary)

```python
# Provider usage
from core import OpenAiProvider, ClaudeProvider

openai_provider = OpenAiProvider(model_name="gpt-4")
claude_provider = ClaudeProvider(model_name="claude-sonnet-4-6")

response = openai_provider.generate("What is 2+2?")
response = claude_provider.generate("Explain normalization.", tools=tool_registry.to_anthropic_tools())

# Tool registry
from core import ToolRegistry

registry = ToolRegistry()
registry.register("get_recipe", get_recipe_func, description="Fetch a recipe by ID")
tools = registry.to_openai_tools()

# Structured output
from core.llm_framework import parse_structured_output

raw = '{"name": "Test", "quantity": 10}'
data = parse_structured_output(raw, {"type": "object", "properties": {"name": {}, "quantity": {}}})

# Memory
from core import ConversationMemory

memory = ConversationMemory()
memory.add_user("Hello")
memory.add_assistant("Hi there!")
messages = memory.get_messages()
```

---

## Deliverable checklist

- [ ] Add `anthropic` to pyproject.toml
- [ ] Implement `LlmProvider` base class
- [ ] Implement `OpenAiProvider`
- [ ] Implement `ClaudeProvider`
- [ ] Implement `ToolRegistry` (register, to_openai_tools, to_anthropic_tools, execute)
- [ ] Implement `parse_structured_output`
- [ ] Create `core/prompts.py` with basic utilities
- [ ] Implement `ConversationMemory`
- [ ] Add exports to `core/__init__.py`
- [ ] Add `tests/unit/test_llm_framework.py` (mocked + optional live test)
- [ ] Run tests, ensure no linter errors
- [ ] Update CLAUDE.md if API surface changes

---

## Notes

- **API keys:** Read from environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). No hardcoding. `.env` is gitignored.
- **Error handling:** Raise on API failures; no silent swallows. Caller decides retry/fallback.
- **Tool format differences:** OpenAI uses `tools=[{"type":"function","function":{...}}]`; Anthropic uses a different structure. ToolRegistry abstracts this.
- **Structured output:** OpenAI `response_format={"type":"json_object"}`; Claude has similar options. Both can return raw JSON string; parsing is unified in `parse_structured_output`.
