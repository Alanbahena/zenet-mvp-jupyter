# Implementation plan: Subtask 4.4 — Structured output parsing and validation

## Goal

Implement utilities to parse and validate JSON-structured outputs from LLM providers, handling both clean JSON and markdown-wrapped responses.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `parse_structured_output(raw: str) -> dict` | External JSON schema validation libraries (`jsonschema`, `pydantic`) |
| `validate_structured_output(data: dict, required_keys: list[str]) -> bool` | Complex schema validation (nested objects, type checking) |
| Markdown code fence stripping (` ```json ... ``` `) | Automatic schema inference |
| ValueError on parse failure with clear messages | Schema generation from examples |
| Top-level key presence validation | Nested key path validation (`"recipe.ingredients[0].name"`) |

---

## Dependencies

- **Task 4.1** — LlmProvider base, OpenAiProvider (done)
- **Task 4.2** — ClaudeProvider (done)
- **Task 4.3** — ToolRegistry (done)
- **External:** None (uses stdlib `json` module only)

---

## Files to Create / Modify

- **Create:** `core/llm_utils.py` — new file for LLM utility functions
- **Modify:** `core/__init__.py` — export new functions
- **Modify:** `tests/unit/test_llm_framework.py` — add tests (or create `test_llm_utils.py`)

---

## Implementation Breakdown

### 1. File location decision

Create `core/llm_utils.py` (separate from `llm_framework.py`):
- Keeps LLM utilities separate from provider classes
- Easier to test independently
- Can grow with future utilities (token counting, retry helpers, etc.)
- Prevents `llm_framework.py` from becoming too large

---

### 2. `parse_structured_output(raw: str) -> dict`

```python
def parse_structured_output(raw: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code fences.

    Supports:
    - Clean JSON: {"name": "value"}
    - Fenced JSON: ```json\n{"name": "value"}\n```
    - Fenced without language: ```\n{"name": "value"}\n```

    Args:
        raw: Raw string response from LLM

    Returns:
        Parsed dictionary

    Raises:
        ValueError: If JSON is invalid or result is not a dict
    """
```

**Algorithm:**
1. Strip leading/trailing whitespace from `raw`
2. Check for markdown code fences:
   - Look for ` ```json ` or ` ``` ` at start
   - If found, extract content between first pair of fences
   - Use string operations (not regex) for MVP simplicity
3. Parse extracted content with `json.loads()`
4. Validate result is a `dict` (not list, string, or primitive)
5. Return the dict

**Error handling:**
- Raise `ValueError` with descriptive message on failure
- Include snippet of problematic input (first 100 chars) in error message
- Handle `json.JSONDecodeError` and convert to `ValueError`

**Edge cases:**
- Empty string → `ValueError("Cannot parse empty string")`
- Not a dict (list `[1,2,3]`) → `ValueError("Expected dict, got list")`
- Not a dict (string `"text"`) → `ValueError("Expected dict, got str")`
- Multiple code fences → Extract first block only
- No closing fence → Try to parse remaining content as JSON

**Implementation approach:**

```python
import json

def parse_structured_output(raw: str) -> dict:
    content = raw.strip()

    if not content:
        raise ValueError("Cannot parse empty string")

    # Handle markdown code fences
    if content.startswith("```"):
        # Find the first newline after opening fence
        first_newline = content.find("\n")
        if first_newline == -1:
            raise ValueError("Invalid code fence format")

        # Find closing fence
        closing_fence = content.find("```", first_newline)
        if closing_fence == -1:
            # No closing fence, try to parse rest of content
            content = content[first_newline + 1:]
        else:
            # Extract content between fences
            content = content[first_newline + 1:closing_fence].strip()

    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        snippet = content[:100] + "..." if len(content) > 100 else content
        raise ValueError(f"Invalid JSON: {e.msg}. Input: {snippet}")

    # Validate it's a dict
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data).__name__}")

    return data
```

---

### 3. `validate_structured_output(data: dict, required_keys: list[str]) -> bool`

```python
def validate_structured_output(data: dict, required_keys: list[str]) -> bool:
    """
    Validate that all required keys are present in the data.

    Only checks top-level keys. Does not validate types or nested structures.

    Args:
        data: Parsed dictionary to validate
        required_keys: List of required top-level keys

    Returns:
        True if all keys present, False otherwise
    """
```

**Algorithm:**
1. Check if each key in `required_keys` exists in `data`
2. Return `True` if all present, `False` if any missing
3. Do NOT raise exceptions (caller decides how to handle)

**Edge cases:**
- Empty `required_keys` → return `True` (vacuous truth)
- Empty `data` with non-empty `required_keys` → return `False`
- Extra keys in `data` → return `True` (only required keys matter)

**Implementation approach:**

```python
def validate_structured_output(data: dict, required_keys: list[str]) -> bool:
    return all(key in data for key in required_keys)
```

**Simple and sufficient for MVP. Future enhancements (out of scope):**
- Type validation (key must be str, int, etc.)
- Nested key paths (e.g., `"recipe.ingredients[0].name"`)
- Value constraints (min/max, regex patterns)
- Optional keys with defaults

---

### 4. Module docstring and exports

Add module docstring to `core/llm_utils.py`:

```python
"""
LLM utility functions for parsing and validating structured outputs.

This module provides utilities for working with LLM responses, particularly
JSON-structured outputs that may be wrapped in markdown code fences.
"""

import json
from typing import Any

__all__ = ["parse_structured_output", "validate_structured_output"]
```

Update `core/__init__.py`:

```python
from core.llm_utils import parse_structured_output, validate_structured_output

__all__ = [
    # ... existing exports ...
    "parse_structured_output",
    "validate_structured_output",
]
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| Empty string | Raise `ValueError("Cannot parse empty string")` |
| Clean JSON dict | Parse and return dict |
| Fenced JSON (` ```json ... ``` `) | Extract content, parse, return dict |
| Fenced without language (` ``` ... ``` `) | Extract content, parse, return dict |
| Multiple code fences | Extract first block only |
| No closing fence | Try to parse content after opening fence |
| JSON list `[1,2,3]` | Raise `ValueError("Expected dict, got list")` |
| JSON string `"text"` | Raise `ValueError("Expected dict, got str")` |
| Invalid JSON | Raise `ValueError` with snippet of input |
| `validate_structured_output({}, [])` | Return `True` |
| `validate_structured_output({}, ["key"])` | Return `False` |
| `validate_structured_output({"a": 1, "b": 2}, ["a"])` | Return `True` |
| `validate_structured_output({"a": 1}, ["a", "b"])` | Return `False` |

---

## Test Strategy

Unit tests in `tests/unit/test_llm_utils.py` (or add to `test_llm_framework.py`):

### parse_structured_output tests

1. **Valid inputs:**
   - Clean JSON: `'{"name": "test"}'` → `{"name": "test"}`
   - Fenced JSON: ` '```json\n{"name": "test"}\n```' ` → `{"name": "test"}`
   - Fenced without language: ` '```\n{"name": "test"}\n```' ` → `{"name": "test"}`
   - Extra whitespace: `'  \n{"name": "test"}\n  '` → `{"name": "test"}`
   - Complex nested dict: `'{"recipe": {"name": "pasta", "ingredients": []}}'`

2. **Invalid inputs (should raise ValueError):**
   - Invalid JSON: `'{"name": invalid}'`
   - Not a dict (list): `'[1, 2, 3]'`
   - Not a dict (string): `'"just a string"'`
   - Not a dict (number): `'42'`
   - Empty string: `''`
   - No closing brace: `'{"name": "test"'`

3. **Edge cases:**
   - Multiple code fences: ` '```json\n{"first": 1}\n```\n```json\n{"second": 2}\n```' ` → `{"first": 1}` (first block)
   - Incomplete fence: ` '```json\n{"name": "test"}' ` (no closing fence) → `{"name": "test"}`
   - Fence with extra text: ` '```json\n{"name": "test"}\n```\nExtra text' ` → `{"name": "test"}`

### validate_structured_output tests

1. **Valid (return True):**
   - All keys present: `validate_structured_output({"a": 1, "b": 2}, ["a", "b"])`
   - Extra keys OK: `validate_structured_output({"a": 1, "b": 2, "c": 3}, ["a"])`
   - Empty required_keys: `validate_structured_output({"a": 1}, [])`
   - Single key: `validate_structured_output({"name": "test"}, ["name"])`

2. **Invalid (return False):**
   - Missing key: `validate_structured_output({"a": 1}, ["a", "b"])`
   - Empty data: `validate_structured_output({}, ["a"])`
   - None values OK: `validate_structured_output({"a": None}, ["a"])` → `True` (key present)

---

## Integration Points

**Where these functions will be used:**

1. **Agent implementations** (Tasks 7-12):
   ```python
   from core import parse_structured_output, validate_structured_output

   response = llm_provider.generate(prompt, structured_output=True)
   data = parse_structured_output(response)

   if validate_structured_output(data, ["restaurant_type", "categories"]):
       # Process valid data
   else:
       # Handle missing keys (retry, log error, use defaults)
   ```

2. **Workflow engine** (Task 6):
   ```python
   result = agent.run(input_data)
   if isinstance(result, str):
       result = parse_structured_output(result)
   ```

3. **Tests** (Phase 4.7):
   - Verify LLM responses are correctly parsed
   - Test error handling with malformed outputs

---

## Deliverable Checklist

- [x] Create `core/llm_utils.py` with module docstring
- [x] Implement `parse_structured_output(raw: str) -> dict`
  - [x] Strip whitespace
  - [x] Handle markdown code fences (` ```json `, ` ``` `) anywhere in response
  - [x] Extract first code block if multiple fences present
  - [x] Parse JSON with `json.loads()`
  - [x] Validate return is dict (raise if list/primitive)
  - [x] Raise `ValueError` with descriptive message and input snippet on failure
- [x] Implement `validate_structured_output(data: dict, required_keys: list[str]) -> bool`
  - [x] Check all required keys present (top-level only)
  - [x] Return `True`/`False` (do not raise)
- [x] Add comprehensive docstrings with type hints
- [x] Export from `core/__init__.py`
- [x] Create `tests/unit/test_llm_utils.py` (or add to `test_llm_framework.py`)
  - [x] Test all valid input formats (19 tests for parse_structured_output)
  - [x] Test all invalid inputs raise ValueError
  - [x] Test edge cases (multiple fences, incomplete fences, text before fence, etc.)
  - [x] Test validate_structured_output with various key combinations (12 tests)
  - [x] Test integration scenarios (5 tests)
- [x] Run tests: `python -m pytest tests/unit/test_llm_utils.py -v` (36/36 passed)
- [x] Run full test suite: `python -m pytest tests/unit/ -v` (324/324 passed)

---

## Notes

- **No external dependencies:** Uses only stdlib `json` module. No `jsonschema`, `pydantic`, or similar libraries.
- **Simplicity over completeness:** MVP focuses on common LLM output formats. Complex validation (nested paths, type checking) deferred to future phases.
- **Error messages:** Include input snippet (first 100 chars) to help debug LLM output issues.
- **Code fence handling:** Uses string operations (not regex) for simplicity. If edge cases arise in testing, can switch to regex.
- **Dict-only return:** `parse_structured_output` only returns dicts, not lists or primitives. If array responses are needed, create separate `parse_structured_list()` function.
- **Validation strategy:** `validate_structured_output` returns bool, doesn't raise. This gives callers flexibility to retry, use defaults, or error as appropriate.
- **Future enhancements (out of scope for 4.4):**
  - Type validation (check value types, not just key presence)
  - Nested key paths (e.g., `"recipe.ingredients[0].name"`)
  - Value constraints (min/max, regex, enums)
  - Schema-based validation (if we add `jsonschema` dependency later)
  - Token counting and truncation helpers
  - Retry/backoff utilities

---

## Time Estimate

- **Implementation:** 30-45 minutes (including docstrings)
- **Tests:** 30-45 minutes (comprehensive test cases)
- **Total:** 1-1.5 hours
