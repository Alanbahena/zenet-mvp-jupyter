# Implementation plan: Subtask 4.1 — Provider base and OpenAI

## Goal

Define the `LlmProvider` abstract base class and implement `OpenAiProvider` as the first concrete provider. This establishes the unified interface for LLM calls and enables OpenAI (GPT) integration.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `LlmProvider` abstract base class with `generate()` | ClaudeProvider (Phase 4.2) |
| `OpenAiProvider` concrete implementation | ToolRegistry, prompts, memory |
| Parameters: `system`, `prompt`, `messages`, `structured_output`, `tools`, `max_tokens`, `temperature` | Streaming, retries, rate limiting |

---

## Dependencies

- **Task 1** — Project setup (done)
- **External:** `openai>=2.20.0` (already in pyproject.toml)
- **API key:** `OPENAI_API_KEY` in `.env`

---

## File to Create

`core/llm_framework.py` (new file)

---

## Breakdown

### 1. Imports and LlmProvider base class

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

"""
LLM provider abstraction for Zenet MVP 0.1.

Provides: LlmProvider (abstract base), OpenAiProvider (concrete).
Pattern mirrors core/persistence.py: abstract interface + concrete implementations.
"""

class LlmProvider(ABC):
    """Abstract base for LLM providers (OpenAI, Claude)."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def generate(
        self,
        *,
        prompt: str | None = None,
        system: str | None = None,
        tools: list | None = None,
        structured_output: bool = False,
        messages: list | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Validate input and delegate to _do_generate. Provide either prompt or messages."""
        self._validate_input(prompt, messages)
        return self._do_generate(
            prompt=prompt,
            system=system,
            tools=tools,
            structured_output=structured_output,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    @abstractmethod
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
        """Provider-specific generation logic. Input is pre-validated."""

    def _validate_input(self, prompt: str | None, messages: list | None) -> None:
        if messages is None and not prompt:
            raise ValueError("Either prompt or messages must be provided")
```

- `generate()` is **concrete** in the base — validates input, then calls abstract `_do_generate()`. This guarantees validation runs for every provider without duplication.
- `_do_generate()` is **abstract** — providers implement this, not `generate()`.
- `from __future__ import annotations` — consistent with all other `core/` modules.
- Module-level docstring at the top of the file — consistent with `data_model.py`, `normalization.py`, etc.
- No `raise NotImplementedError` inside `@abstractmethod` — the decorator already prevents instantiation if `_do_generate` isn't overridden; the body is unreachable.
- All arguments are keyword-only (no positional after `self`).
- `generate()` returns a plain `str`.

---

### 2. Input validation rule

Enforced in `LlmProvider._validate_input()` (base class), called automatically by `generate()` before `_do_generate()`:

1. If both `prompt` and `messages` are missing/empty → raise `ValueError`.
2. If `messages` is provided → ignore `prompt`; use `messages` as the full conversation.
3. If `prompt` is provided (and no `messages`) → treat as single-turn user message.

```python
def _validate_input(self, prompt: str | None, messages: list | None) -> None:
    if messages is None and not prompt:
        raise ValueError("Either prompt or messages must be provided")
```

Because validation lives in the base class `generate()`, providers never need to call it themselves — it is guaranteed to run before `_do_generate()` is invoked.

---

### 3. OpenAiProvider skeleton

```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load .env once at module import time

class OpenAiProvider(LlmProvider):
    """OpenAI GPT provider. Uses OPENAI_API_KEY from environment."""

    def __init__(self, model_name: str = "gpt-4o") -> None:
        super().__init__(model_name)
        self.client = OpenAI()  # Reads OPENAI_API_KEY from env automatically

    def _do_generate(self, *, prompt, system, tools, structured_output, messages, max_tokens, temperature) -> str:
        # Implementation in steps 4–6 below
```

- Default model: `gpt-4o`.
- `OpenAI()` reads `OPENAI_API_KEY` from environment; no hardcoding.
- `load_dotenv()` is called at module level so `.env` is loaded automatically when `llm_framework` is imported. If `python-dotenv` is not yet in `pyproject.toml`, add it: `uv add python-dotenv`.
- Implements `_do_generate()`, not `generate()` — validation is handled by the base class.

---

### 4. Build the messages list for OpenAI

OpenAI expects `[{role, content}, ...]`.

Logic:

1. If `messages` is provided → use as-is (they already have `role` and `content`). If `system` is provided, prepend `{"role": "system", "content": system}` to `messages`.
2. Else (prompt only) → build list: if `system`, prepend system message; then add `{"role": "user", "content": prompt}`.

Example:

```python
if messages is not None:
    api_messages = []
    if system:
        api_messages.append({"role": "system", "content": system})
    api_messages.extend(messages)
else:
    api_messages = []
    if system:
        api_messages.append({"role": "system", "content": system})
    api_messages.append({"role": "user", "content": prompt})
```

---

### 5. Build kwargs for `client.chat.completions.create`

```python
kwargs = {
    "model": self.model_name,
    "messages": api_messages,
    "max_tokens": max_tokens,
    "temperature": temperature,
}
if tools:
    kwargs["tools"] = tools  # Pass through as-is
if structured_output:
    kwargs["response_format"] = {"type": "json_object"}
```

- **`tools` format in Phase 4.1:** `tools` is passed through directly to the OpenAI API. In Phase 4.1, callers who pass `tools` must already format them as OpenAI expects: `[{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}]`. Correct formatting will be the responsibility of `ToolRegistry` (Phase 4.3) — until then, `tools` will typically be `None`.
- `structured_output=True` → add `response_format={"type": "json_object"}`.

---

### 6. Extract and return the response

```python
response = self.client.chat.completions.create(**kwargs)
content = response.choices[0].message.content
# content is None when the model issued a tool call instead of a text response.
# In Phase 4.1 (no ToolRegistry yet), this is unlikely but handled defensively.
# Callers receiving "" should check if a tool_call was triggered.
return content if content is not None else ""
```

- `message.content` can be `None` when the model returns a tool call with no accompanying text. Returning `""` is a safe fallback for Phase 4.1, but callers should be aware this is a silent signal — not an error. Once `ToolRegistry` is in place (Phase 4.3), tool call responses will be handled explicitly.

---

### 7. Exports in core/__init__.py

Add:

```python
from core.llm_framework import LlmProvider, OpenAiProvider
```

And add `"LlmProvider"` and `"OpenAiProvider"` to `__all__`.

---

## Edge cases

| Case | Behavior |
|------|----------|
| `prompt=None`, `messages=None` | Raise `ValueError` |
| `prompt=""`, `messages=None` | Raise `ValueError` |
| `prompt="Hi"`, `messages=[...]` | Use `messages`, ignore `prompt` |
| `system=None` | Do not add system message |
| `structured_output=True` | Add `response_format={"type": "json_object"}` |
| `tools=None` | Do not add `tools` to kwargs |
| Missing `OPENAI_API_KEY` | Let `OpenAI()` raise (SDK handles this) |

---

## Test strategy

Unit tests with mocked API (`unittest.mock.patch` on `client.chat.completions.create`):

1. `OpenAiProvider().generate(prompt="Hi")` → returns string (mocked).
2. `generate(prompt=None, messages=None)` → raises `ValueError`.
3. `generate(prompt="", messages=None)` → raises `ValueError` (empty string is also invalid).
4. `generate(messages=[{"role":"user","content":"Hi"}])` → uses messages, ignores `prompt`.
5. `generate(prompt="Hi", system="You are helpful")` → system message prepended to messages list.
6. `generate(prompt="Hi", structured_output=True)` → `response_format={"type":"json_object"}` in API call.
7. `OpenAiProvider(model_name="gpt-4-turbo")` → uses custom model name.
8. `generate(prompt="Hi", tools=[...])` → `tools` key present in API call kwargs.

Optional: one live integration test in `TestLiveProviders` class, decorated with:
```python
@unittest.skipIf(not os.getenv("OPENAI_API_KEY"), "No OPENAI_API_KEY set")
```

---

## What NOT to implement in 4.1

- ClaudeProvider
- ToolRegistry
- parse_structured_output / validate_structured_output
- prompts.py
- ConversationMemory

---

## Deliverable checklist

- [x] Create `core/llm_framework.py` with module-level docstring and `from __future__ import annotations`
- [x] `LlmProvider` is abstract with concrete `generate()` + abstract `_do_generate()` + `_validate_input()`
- [x] `OpenAiProvider` implements `_do_generate()`: builds messages, calls API, returns string
- [x] `load_dotenv()` called at module level in `llm_framework.py`; add `python-dotenv` via `uv add python-dotenv` if not present
- [x] Add exports to `core/__init__.py`: `LlmProvider`, `OpenAiProvider`; add to `__all__`
- [x] Add unit tests in `tests/unit/test_llm_framework.py` (9 mocked cases + `TestLiveProviders` with `skipIf`)
- [x] Run `python -m pytest tests/unit/test_llm_framework.py -v` — 9 passed (live test requires network)
- [ ] Manual smoke test: `OpenAiProvider().generate(prompt="Say hello")` returns string (requires `OPENAI_API_KEY` + network)

---

## Notes

- **API key:** `OPENAI_API_KEY` must be in `.env`. `load_dotenv()` in `llm_framework.py` loads it at import time. The OpenAI SDK then reads it from the environment automatically — no hardcoding.
- **Error handling:** Let SDK exceptions propagate as-is. No custom wrapper in MVP.
- **`tools` format:** In Phase 4.1, callers must pre-format tools as OpenAI expects. `ToolRegistry` (Phase 4.3) will handle formatting — until then, `tools` will typically be `None`.
- **Template method pattern:** `generate()` = validate + delegate. `_do_generate()` = provider logic. Never override `generate()` in subclasses.
- **`content is None`:** A silent `""` return signals a tool call response without text. Not an error in Phase 4.1 — will be handled explicitly once `ToolRegistry` exists.
