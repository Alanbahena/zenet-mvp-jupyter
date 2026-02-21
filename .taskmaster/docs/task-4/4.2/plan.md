# Implementation plan: Subtask 4.2 — Claude provider

## Goal

Implement `ClaudeProvider` as the second concrete provider, enabling Anthropic Claude integration. `ClaudeProvider` uses the same `LlmProvider` interface as `OpenAiProvider`, with Anthropic-specific handling for system prompts, tools, and structured output.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `ClaudeProvider` implementing `_do_generate()` | ToolRegistry (Phase 4.3) — tools passed through in Anthropic format |
| Add `anthropic` dependency | parse_structured_output, prompts, memory |
| System via dedicated `system=` param | Streaming, retries, rate limiting |

---

## Dependencies

- **Task 4.1** — LlmProvider base, OpenAiProvider (done)
- **External:** `anthropic` (to add via `uv add anthropic`)
- **API key:** `ANTHROPIC_API_KEY` in `.env`

---

## Files to Modify

- `core/llm_framework.py` — add ClaudeProvider
- `pyproject.toml` — add `anthropic` dependency
- `core/__init__.py` — export ClaudeProvider

---

## Anthropic vs OpenAI (key differences)

| Aspect | OpenAI | Anthropic Claude |
|--------|--------|------------------|
| System prompt | Prepended as `{"role": "system", "content": system}` | Dedicated `system=` parameter (string) |
| Messages | `[{"role": "user/assistant", "content": "..."}]` | Same structure; `content` can be string or array of blocks |
| Tools format | `[{"type": "function", "function": {...}}]` | `[{"name": "...", "description": "...", "input_schema": {...}}]` |
| Structured output | `response_format={"type": "json_object"}` | No native JSON mode; append instruction to system |
| Response extraction | `response.choices[0].message.content` | `response.content[0].text` (first text block) |

---

## Breakdown

### 1. Add anthropic dependency

```bash
uv add anthropic
uv export --no-dev -o requirements.txt
```

Or manually add to `pyproject.toml`:

```toml
dependencies = [
    "openai>=2.20.0",
    "python-dotenv>=1.0.0",
    "anthropic>=0.40.0",
]
```

---

### 2. ClaudeProvider skeleton

```python
from anthropic import Anthropic

class ClaudeProvider(LlmProvider):
    """Anthropic Claude provider. Uses ANTHROPIC_API_KEY from environment."""

    def __init__(self, model_name: str = "claude-sonnet-4-6") -> None:
        super().__init__(model_name)
        self.client = Anthropic()

    def _do_generate(
        self,
        *,
        prompt: str | None,
        system: str | None,
        tools: list | None,
        structured_output: bool,
        messages: list | None,
        max_tokens: int,
        temperature: float,
    ) -> str:
        # Implementation in steps 3–7 below
```

- Default model: `claude-sonnet-4-6` (latest Sonnet as per CLAUDE.md).
- `Anthropic()` reads `ANTHROPIC_API_KEY` from env (load_dotenv already called in 4.1).
- Implements `_do_generate()`, not `generate()` — validation is handled by base class.

---

### 3. Build messages for Anthropic

Anthropic expects `[{"role": "user"|"assistant", "content": "..."}]`. No `system` role in messages — system is passed separately.

**If `messages` is provided:**
- Use as-is. Filter out any `{"role": "system", ...}` entries (Anthropic does not allow system in messages; we pass it via `system=`).
- If our messages include system, strip them and pass system via `system=` param.

**If `prompt` only:**
- Build: `[{"role": "user", "content": prompt}]`

**Content format:** Anthropic accepts string or `[{"type": "text", "text": "..."}]`. For MVP, plain strings are sufficient.

```python
# Filter out system messages from our format (if any)
if messages is not None:
    api_messages = [m for m in messages if m.get("role") != "system"]
else:
    api_messages = [{"role": "user", "content": prompt or ""}]
```

---

### 4. Build system string for Anthropic

- If `system` is provided, use it.
- If `structured_output=True`, append JSON instruction to system (Anthropic has no native JSON mode):

```python
effective_system = system or ""
if structured_output:
    json_instruction = " Respond with valid JSON only. Do not include markdown code fences."
    effective_system = (effective_system + json_instruction).strip() if effective_system else "Respond with valid JSON only. Do not include markdown code fences."
```

- Pass `system=effective_system` to API only if non-empty. Anthropic allows `system` to be omitted.

---

### 5. Build kwargs for `client.messages.create`

```python
kwargs: dict = {
    "model": self.model_name,
    "max_tokens": max_tokens,
    "messages": api_messages,
}
if effective_system:
    kwargs["system"] = effective_system
if temperature != 1.0:  # Anthropic's default is 1.0; only pass if different
    kwargs["temperature"] = temperature
if tools:
    kwargs["tools"] = tools  # Must be Anthropic format: [{name, description, input_schema}]
```

- Anthropic uses `max_tokens` (required). Our `generate()` already passes it.
- `temperature` — Anthropic supports it; pass through.
- `tools` — In Phase 4.2, callers must pass Anthropic format. ToolRegistry (4.3) will provide `to_anthropic_tools()`.

---

### 6. Call API and extract response

```python
response = self.client.messages.create(**kwargs)
```

Response has `content`: list of blocks. Each block has `type` and either `text` (for TextBlock) or `input`/`name` (for tool_use).

**Extract text:**
- Iterate `response.content` and find the first block with `type == "text"`; return its `text`.
- If no text block (e.g. tool_use only), return `""`.

```python
if not response.content:
    return ""
for block in response.content:
    if hasattr(block, "text") and block.text:
        return block.text
return ""
```

- Anthropic SDK returns typed objects; `block.type` and `block.text` are typical. Verify against actual SDK response structure.

---

### 7. Exports and module docstring

- Add `ClaudeProvider` to `core/__init__.py` import and `__all__`.
- Update `core/llm_framework.py` module docstring to include ClaudeProvider.

---

## Tool format (Phase 4.2 vs 4.3)

| Phase | Responsibility |
|-------|----------------|
| 4.2 | Pass `tools` through as-is. Callers must provide Anthropic format: `[{"name": "...", "description": "...", "input_schema": {...}}]` |
| 4.3 | ToolRegistry will provide `to_anthropic_tools()` — converts provider-agnostic registry to Anthropic format |

Until 4.3, `tools` will typically be `None`. If passed, format must match Anthropic.

---

## Edge cases

| Case | Behavior |
|------|----------|
| `messages` contains system role | Filter out; pass system via `system=` if provided |
| `structured_output=True`, `system=None` | Use system = "Respond with valid JSON only." |
| `response.content` is empty or None | Return `""` |
| `response.content` has no text block | Return `""` (e.g. tool_use without text) |
| Missing `ANTHROPIC_API_KEY` | Let `Anthropic()` raise (SDK handles it) |
| Empty `api_messages` | Should not occur — base validation ensures prompt or messages |

---

## Test strategy

Unit tests with mocked API (`unittest.mock.patch` on `anthropic.Anthropic` or `client.messages.create`):

1. `ClaudeProvider().generate(prompt="Hi")` → returns string.
2. `generate(prompt="Hi", system="You are helpful")` → system passed as `system=` param, not in messages.
3. `generate(messages=[{"role": "user", "content": "Hi"}])` → messages passed; system not in messages.
4. `generate(prompt="Hi", structured_output=True)` → JSON instruction appended to system.
5. `ClaudeProvider(model_name="claude-opus-4-6")` → uses custom model.
6. `generate(prompt="Hi", tools=[...])` → tools passed to API.
7. Response with no text block (tool_use only) → returns `""`.

Optional: live integration test (skipIf no ANTHROPIC_API_KEY):

```python
@unittest.skipIf(not os.getenv("ANTHROPIC_API_KEY"), "No ANTHROPIC_API_KEY set")
def test_claude_provider_live_call(self) -> None:
    provider = ClaudeProvider()
    result = provider.generate(prompt="Say hello in one word.")
    self.assertIsInstance(result, str)
    self.assertGreater(len(result), 0)
```

---

## Deliverable checklist

- [ ] Add `anthropic` to pyproject.toml and run `uv sync`
- [ ] Regenerate `requirements.txt` via `uv export --no-dev -o requirements.txt`
- [ ] Implement `ClaudeProvider` in `core/llm_framework.py`
- [ ] Use dedicated `system=` param (do not inject system into messages)
- [ ] When `structured_output=True`, append JSON instruction to system
- [ ] Extract text from first text block in `response.content`; return `""` if none
- [ ] Filter system role from messages if present
- [ ] Add `ClaudeProvider` to `core/__init__.py` exports
- [ ] Add unit tests in `tests/unit/test_llm_framework.py` (mocked + optional live)
- [ ] Run `python -m pytest tests/unit/test_llm_framework.py -v`

---

## Notes

- **API key:** `ANTHROPIC_API_KEY` in `.env`; `load_dotenv()` from 4.1 loads it at import.
- **Tool format:** Anthropic uses `{name, description, input_schema}`; OpenAI uses `{type: "function", function: {name, description, parameters}}`. ToolRegistry (4.3) will abstract this.
- **structured_output:** Anthropic has no `response_format`; we rely on system instruction. Callers should set `temperature=0` for deterministic JSON.
- **Message content:** Anthropic accepts string or array of blocks. We use strings for MVP simplicity.
