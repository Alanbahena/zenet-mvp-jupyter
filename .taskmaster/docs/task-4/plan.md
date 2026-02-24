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

| Provider | Default model | Other available |
|----------|---------------|-----------------|
| OpenAI | `gpt-4o` | `gpt-4-turbo`, `gpt-3.5-turbo` |
| Claude | `claude-sonnet-4-5` | `claude-sonnet-4-6`, `claude-opus-4-6`, `claude-haiku-4-5-20251001` |

---

## Breakdown

### Phase 4.1 — Provider base and OpenAI

**Files:** `core/llm_framework.py`

- Define `LlmProvider` abstract base class:
  - `__init__(self, model_name: str)`
  - `generate(self, prompt: str, *, system: str | None = None, tools: list | None = None, structured_output: bool = False, messages: list | None = None, max_tokens: int = 4096, temperature: float = 0.7) -> str`
  - All providers accept a string `prompt` or a `messages` list (for multi-turn)
  - **Precedence rule:** if `messages` is provided, it overrides `prompt`; if neither is provided, raise `ValueError`
  - `system` is passed separately because OpenAI injects it as a system-role message while Claude passes it as a dedicated `system=` API param — providers handle the difference internally
  - `structured_output=True` signals JSON mode; callers should set `temperature=0` for deterministic outputs
- Implement `OpenAiProvider`:
  - Uses `openai.OpenAI()` (reads `OPENAI_API_KEY` from env)
  - Default model: `gpt-4o`
  - Injects `system` as `{"role": "system", "content": system}` prepended to messages
  - Maps `tools` to OpenAI tools format
  - Maps `structured_output=True` to `response_format={"type": "json_object"}`
  - Returns `response.choices[0].message.content`

**Design choice:** `generate` returns a plain string. Structured output parsing is separate (Phase 4.4).

---

### Phase 4.2 — Claude provider

**Files:** `core/llm_framework.py`

- Add `anthropic` to `pyproject.toml`: `uv add anthropic`
- Regenerate `requirements.txt`: `uv export --no-dev -o requirements.txt`
- Implement `ClaudeProvider`:
  - Uses `anthropic.Anthropic()` (reads `ANTHROPIC_API_KEY` from env)
  - Default model: `claude-sonnet-4-5`
  - Passes `system` via the dedicated `system=` parameter in the Anthropic API (not injected into messages list)
  - Maps `tools` to Anthropic tool format (slightly different from OpenAI)
  - When `structured_output=True`: appends JSON instruction to system prompt (Anthropic does not have a native JSON mode equivalent to OpenAI's `response_format`)
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
- Tool schema: use JSON Schema for parameters; `parameters_schema` must be provided explicitly (MVP — no automatic inference from function signatures)
- `infer_schema(func)` helper is **out of scope for MVP**; deferred to a later task

---

### Phase 4.4 — Structured output parsing and validation

**Files:** `core/llm_framework.py` or `core/llm_utils.py`

- `parse_structured_output(raw: str) -> dict`:
  - Parse JSON from raw string (handle markdown code blocks like ` ```json ... ``` `)
  - Returns parsed `dict`; raises `ValueError` with a clear message on failure
- `validate_structured_output(data: dict, required_keys: list[str]) -> bool`:
  - Manual key-presence check — no external library
  - Returns `False` (does not raise) when keys are missing, so callers decide how to handle
- **Decision: no `jsonschema` dependency in MVP** — manual validation is sufficient for the structured outputs agents will use (restaurant classification, ingredient extraction, etc.)

---

### Phase 4.5 — Prompt utilities

**Files:** `core/prompts.py`

- **Decision: use `@dataclass PromptTemplate`** (consistent with project's dataclass convention) over plain functions:
  ```python
  @dataclass
  class PromptTemplate:
      name: str
      system: str
      user_template: str  # supports {variable} placeholders

      def render(self, **kwargs) -> tuple[str, str]:
          """Returns (system, user_prompt) with variables substituted."""
  ```
- Helper functions:
  - `format_system_prompt(role: str, context: str | None = None) -> str`
  - `format_user_prompt(template: str, **kwargs) -> str` — simple `str.format_map` wrapper
- Restaurant-specific prompt stubs (minimal, to support Tasks 7–11):
  - `INGREDIENT_EXTRACTION_PROMPT`, `RECIPE_ANALYSIS_PROMPT` as `PromptTemplate` instances
- No templating engine — `str.format_map` is sufficient for MVP

---

### Phase 4.6 — Conversation memory

**Files:** `core/llm_framework.py` or `core/memory.py`

- `ConversationMemory` class:
  - `__init__(self, max_turns: int = 20)`
  - `add_user(message: str) -> None`
  - `add_assistant(message: str) -> None`
  - `get_messages() -> list[dict]` — returns `[{"role": "user", "content": "..."}, ...]`, trimmed to last `max_turns` messages
  - `clear() -> None`
  - `to_dict() -> dict` — serializes to dict (project convention; enables future persistence via `DataLake`)
  - `from_dict(cls, data: dict) -> ConversationMemory` — classmethod deserializer
- **Truncation strategy:** trim by `max_turns` (count of messages), not by token count — token counting is complex and deferred
- In-memory only in MVP; persistence via `DataLake` can be layered on in Task 5
- `LlmProvider.generate` accepts optional `messages`; if provided, it overrides `prompt`

---

### Phase 4.7 — Exports and tests

**Files:** `core/__init__.py`, `tests/unit/test_llm_framework.py`

- Export from `core/__init__.py`:
  - `LlmProvider`, `OpenAiProvider`, `ClaudeProvider`
  - `ToolRegistry`, `ConversationMemory`
  - `parse_structured_output`, `validate_structured_output`
  - From `core/prompts`: `PromptTemplate`, `format_system_prompt`, `format_user_prompt`
- Unit tests (with mocked API calls via `unittest.mock.patch`):
  - Provider interface: `OpenAiProvider` and `ClaudeProvider` return string from `generate` (mock `openai.OpenAI` / `anthropic.Anthropic`)
  - `generate()` with `messages` overrides `prompt`; missing both raises `ValueError`
  - `system` param: verify it is injected correctly per provider
  - ToolRegistry: register, execute, `to_openai_tools`, `to_anthropic_tools`
  - Structured output: parse valid JSON, parse fenced JSON block, raise `ValueError` on invalid
  - `validate_structured_output`: all keys present → `True`; missing key → `False`
  - ConversationMemory: add, get, clear, `max_turns` trimming, `to_dict`/`from_dict` round-trip
  - PromptTemplate: `render()` substitution, missing variable → `KeyError`
- Live integration tests (one real call per provider):
  - Decorated with `@unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OpenAI key")` / `@unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No Anthropic key")`
  - Kept in a separate class `TestLiveProviders` at the bottom of the test file

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

- [ ] Add `anthropic` to pyproject.toml via `uv add anthropic`
- [ ] Regenerate `requirements.txt` via `uv export --no-dev -o requirements.txt`
- [ ] Implement `LlmProvider` abstract base class (with `system`, `max_tokens`, `temperature`, `messages` params)
- [ ] Implement `OpenAiProvider` (default model: `gpt-4o`)
- [ ] Implement `ClaudeProvider` (default model: `claude-sonnet-4-5`)
- [ ] Implement `ToolRegistry` (register, to_openai_tools, to_anthropic_tools, execute)
- [ ] Implement `parse_structured_output` and `validate_structured_output`
- [ ] Create `core/prompts.py` with `PromptTemplate`, `format_system_prompt`, `format_user_prompt`, and agent prompt stubs
- [ ] Implement `ConversationMemory` (with `max_turns`, `to_dict`, `from_dict`)
- [ ] Add exports to `core/__init__.py`
- [ ] Add `tests/unit/test_llm_framework.py` (mocked unit tests + `TestLiveProviders` with `skipIf` guards)
- [ ] Run full test suite: `python -m pytest tests/ -v`
- [ ] Update CLAUDE.md if API surface changes

---

## Notes

- **API keys:** Read from environment (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`). No hardcoding. `.env` is gitignored.
- **Error handling:** Let SDK exceptions propagate as-is (no custom `LlmApiError` wrapper in MVP). Caller decides retry/fallback. No silent swallows.
- **Tool format differences:** OpenAI uses `tools=[{"type":"function","function":{...}}]`; Anthropic uses a different structure. `ToolRegistry` abstracts this via `to_openai_tools()` and `to_anthropic_tools()`.
- **Structured output:** OpenAI uses `response_format={"type":"json_object"}`; Claude uses a JSON instruction appended to the system prompt. Both return a raw JSON string; parsing is unified in `parse_structured_output`.
- **No `jsonschema` dependency:** Manual key-presence validation via `validate_structured_output` is sufficient for MVP.
- **`messages` vs `prompt`:** If `messages` is provided to `generate()`, it takes precedence over `prompt`. If neither is provided, `ValueError` is raised.
- **`system` param handling:** OpenAI prepends `{"role":"system","content":system}` to the messages list; Anthropic passes it as the dedicated `system=` argument — both handled internally by each provider class.

---

## Future considerations

- **LLM guardrails:** Task 4 includes output validation via `parse_structured_output` and `validate_structured_output`, which covers schema enforcement. A dedicated guardrails task (depending on Task 4, and optionally Task 5) could add:
  - Input guardrails: prompt injection heuristics, input length limits, PII filtering
  - Output guardrails beyond schema: content filtering, output length caps
  - Safety: redacting sensitive restaurant data before logging or in certain contexts
- Introduce when agents are user-facing (Tasks 7+) or when compliance/safety requirements emerge.

- **Token counting:** `ConversationMemory` truncates by `max_turns` (message count), not tokens. A token counter could add:
  - Context-limit checks (e.g. prompt + response vs model max tokens)
  - Token-based memory truncation for long conversations
  - Cost estimation (APIs charge per token)
  - Provider-specific helpers: `tiktoken` for OpenAI; Anthropic tokenizer for Claude
- Introduce when memory truncation becomes inaccurate, cost tracking is needed, or prompts approach model limits.
