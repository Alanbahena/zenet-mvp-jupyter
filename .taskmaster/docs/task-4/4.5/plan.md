# Implementation plan: Subtask 4.5 — Prompt utilities

## Goal

Create a prompt templating system using dataclasses for consistent prompt construction across agents. Provides `PromptTemplate` dataclass, helper functions for formatting, and pre-built templates for common restaurant operations.

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| `PromptTemplate` dataclass with `render()` method | External templating engines (Jinja2, etc.) |
| `format_system_prompt(role, context)` helper | Complex template validation |
| `format_user_prompt(template, **kwargs)` wrapper | Nested variable substitution (`{obj.field}`) |
| 2-3 pre-built restaurant-specific templates | Comprehensive template library (agents build their own) |
| Simple `str.format_map()` substitution | Template inheritance or composition |

---

## Dependencies

- **Task 4.1** — LlmProvider base, OpenAiProvider (done)
- **Task 4.2** — ClaudeProvider (done)
- **Task 4.3** — ToolRegistry (done)
- **Task 4.4** — Structured output parsing (done)
- **External:** None (stdlib only)

---

## Files to Create / Modify

- **Create:** `core/prompts.py` — new file for prompt utilities
- **Modify:** `core/__init__.py` — export PromptTemplate and helpers
- **Create:** `tests/unit/test_prompts.py` — new test file

---

## Implementation Breakdown

### 1. PromptTemplate dataclass

```python
from dataclasses import dataclass
from typing import Any

@dataclass
class PromptTemplate:
    """
    Template for LLM prompts with variable substitution.

    Attributes:
        name: Identifier for this template (e.g., "ingredient_extraction")
        system: System prompt (role, context, instructions)
        user_template: User prompt template with {variable} placeholders

    Example:
        >>> template = PromptTemplate(
        ...     name="recipe_analysis",
        ...     system="You are a recipe analyst.",
        ...     user_template="Analyze this recipe: {recipe_text}"
        ... )
        >>> system, user = template.render(recipe_text="Pasta carbonara...")
    """
    name: str
    system: str
    user_template: str

    def render(self, **kwargs: Any) -> tuple[str, str]:
        """
        Render the template with provided variables.

        Args:
            **kwargs: Variables to substitute in user_template

        Returns:
            Tuple of (system_prompt, user_prompt)

        Raises:
            KeyError: If a required variable is not provided

        Example:
            >>> template.render(recipe_text="Pasta with eggs")
            ("You are a recipe analyst.", "Analyze this recipe: Pasta with eggs")
        """
        user_prompt = self.user_template.format_map(kwargs)
        return (self.system, user_prompt)
```

**Design decisions:**
- Use `format_map()` instead of `format()` for better error messages
- Return tuple `(system, user)` — matches LlmProvider.generate() signature
- Let `KeyError` raise if variable missing (fail fast, catches bugs early)
- No validation of variables — simple and explicit

**Edge cases:**
- Empty `user_template` → returns `("system", "")`
- No variables in template → `render()` ignores kwargs
- Extra kwargs not in template → ignored (permissive)
- Missing required variable → raises `KeyError`

---

### 2. Helper function: `format_system_prompt()`

```python
def format_system_prompt(role: str, context: str | None = None) -> str:
    """
    Build a system prompt from role and optional context.

    Args:
        role: The role description (e.g., "recipe analyst", "inventory manager")
        context: Optional additional context (e.g., "for an Italian restaurant")

    Returns:
        Formatted system prompt string

    Example:
        >>> format_system_prompt("recipe analyst")
        "You are a recipe analyst."

        >>> format_system_prompt("recipe analyst", "for an Italian restaurant")
        "You are a recipe analyst for an Italian restaurant."
    """
    if context:
        return f"You are a {role} {context}."
    return f"You are a {role}."
```

**Design decisions:**
- Simple pattern: "You are a {role} {context}."
- Context is optional (most prompts won't need it)
- Always ends with period for consistency
- Lowercase role (natural language)

**Usage:**
```python
system = format_system_prompt("data extraction specialist", "for Zenet restaurant operations")
# "You are a data extraction specialist for Zenet restaurant operations."
```

---

### 3. Helper function: `format_user_prompt()`

```python
def format_user_prompt(template: str, **kwargs: Any) -> str:
    """
    Format a user prompt template with variables.

    Simple wrapper around str.format_map() for consistency.

    Args:
        template: Template string with {variable} placeholders
        **kwargs: Variables to substitute

    Returns:
        Formatted prompt string

    Raises:
        KeyError: If a required variable is not provided

    Example:
        >>> format_user_prompt("Extract ingredients from: {text}", text="Pasta recipe...")
        "Extract ingredients from: Pasta recipe..."
    """
    return template.format_map(kwargs)
```

**Design decisions:**
- Thin wrapper over `format_map()` for API consistency
- Could be replaced by direct `format_map()` calls, but provides:
  - Consistent naming with `format_system_prompt()`
  - Future extensibility (e.g., escaping, validation)
  - Clear intent in agent code

---

### 4. Pre-built restaurant templates

Create 2-3 minimal templates to support agent development (Tasks 7-11):

```python
# Template 1: Ingredient extraction
INGREDIENT_EXTRACTION_PROMPT = PromptTemplate(
    name="ingredient_extraction",
    system=format_system_prompt(
        "ingredient extraction specialist",
        "helping restaurant operators structure their recipe data"
    ),
    user_template="""Extract all ingredients from the following recipe text and return them as a JSON array.

Each ingredient should have:
- name (string): ingredient name
- quantity (number or null if not specified)
- unit (string or null if not specified)

Recipe text:
{recipe_text}

Return only valid JSON, no additional text."""
)

# Template 2: Recipe classification
RECIPE_CLASSIFICATION_PROMPT = PromptTemplate(
    name="recipe_classification",
    system=format_system_prompt(
        "recipe classification specialist",
        "for restaurant operations"
    ),
    user_template="""Classify this recipe into the appropriate category.

Available categories: {categories}

Recipe:
Name: {recipe_name}
Description: {recipe_description}

Return JSON with the structure:
{{"category": "category_name", "confidence": 0.0-1.0}}"""
)

# Template 3: Inventory item suggestion (optional - add if time allows)
INVENTORY_ITEM_SUGGESTION_PROMPT = PromptTemplate(
    name="inventory_item_suggestion",
    system=format_system_prompt(
        "inventory management assistant",
        "helping organize restaurant inventory"
    ),
    user_template="""Given this ingredient from a recipe, suggest the corresponding inventory item.

Ingredient: {ingredient_name}
Recipe context: {recipe_name}

Available inventory families: {families}

Return JSON:
{{"inventory_item_name": "suggested name", "family": "family_name", "reasoning": "brief explanation"}}"""
)
```

**Design decisions:**
- Start with 2-3 templates (more can be added as agents are built)
- Focus on core operations: extraction, classification, inventory linking
- Include JSON structure examples in templates (guides LLM output)
- Use multi-line strings for readability
- Templates use `format_system_prompt()` for consistency

---

### 5. Module exports and docstring

```python
"""
Prompt templating utilities for LLM interactions.

Provides PromptTemplate dataclass and helper functions for building
consistent prompts across agents. Includes pre-built templates for
common restaurant operations.
"""

from dataclasses import dataclass
from typing import Any

__all__ = [
    "PromptTemplate",
    "format_system_prompt",
    "format_user_prompt",
    "INGREDIENT_EXTRACTION_PROMPT",
    "RECIPE_CLASSIFICATION_PROMPT",
    "INVENTORY_ITEM_SUGGESTION_PROMPT",
]
```

Update `core/__init__.py`:

```python
from core.prompts import (
    PromptTemplate,
    format_system_prompt,
    format_user_prompt,
    INGREDIENT_EXTRACTION_PROMPT,
    RECIPE_CLASSIFICATION_PROMPT,
    INVENTORY_ITEM_SUGGESTION_PROMPT,
)

__all__ = [
    # ... existing exports ...
    "PromptTemplate",
    "format_system_prompt",
    "format_user_prompt",
    "INGREDIENT_EXTRACTION_PROMPT",
    "RECIPE_CLASSIFICATION_PROMPT",
    "INVENTORY_ITEM_SUGGESTION_PROMPT",
]
```

---

## Edge Cases

| Case | Behavior |
|------|----------|
| `render()` with no variables needed | Returns `(system, user_template)` unchanged |
| `render()` with extra kwargs | Ignores extra kwargs (permissive) |
| `render()` missing required variable | Raises `KeyError` with variable name |
| Empty `user_template` | Valid; returns `(system, "")` |
| Empty `system` | Valid; returns `("", user)` |
| Template with `{{escaped}}` braces | Uses `format_map()` escaping rules |
| `format_system_prompt(role, None)` | Same as no context provided |
| `format_system_prompt("", "context")` | Returns `"You are a  context."` (valid but odd) |
| Multi-line templates | Supported (use `"""` strings) |

---

## Test Strategy

### PromptTemplate tests

1. **Basic instantiation and render:**
   - Create template, call `render()` with all variables
   - Verify `(system, user)` tuple returned
   - Verify variables substituted correctly

2. **Missing variable:**
   - `render()` without required variable raises `KeyError`
   - Error message includes variable name

3. **Extra kwargs:**
   - `render()` with extra variables succeeds (ignores extras)

4. **No variables:**
   - Template with no `{placeholders}` renders successfully

5. **Multi-line template:**
   - Template with newlines preserves formatting

6. **Complex substitution:**
   - Multiple variables in template
   - Same variable used multiple times

### Helper function tests

7. **`format_system_prompt()` without context:**
   - Returns "You are a {role}."

8. **`format_system_prompt()` with context:**
   - Returns "You are a {role} {context}."

9. **`format_user_prompt()` simple:**
   - Substitutes variables correctly

10. **`format_user_prompt()` missing variable:**
    - Raises `KeyError`

### Pre-built template tests

11. **INGREDIENT_EXTRACTION_PROMPT:**
    - Can render with `recipe_text`
    - System and user_template are non-empty

12. **RECIPE_CLASSIFICATION_PROMPT:**
    - Can render with `categories`, `recipe_name`, `recipe_description`
    - Contains JSON structure example

13. **All templates have unique names:**
    - No duplicate template names

### Integration tests

14. **Use with LlmProvider:**
    - Render template and pass to `generate()`
    - Verify system and user are used correctly

---

## Integration Points

**Where these will be used:**

1. **Agent implementations (Tasks 7-12):**
   ```python
   from core import INGREDIENT_EXTRACTION_PROMPT, OpenAiProvider

   provider = OpenAiProvider()
   template = INGREDIENT_EXTRACTION_PROMPT

   system, user = template.render(recipe_text="Pasta: 200g flour, 2 eggs")
   response = provider.generate(user, system=system, structured_output=True)
   ```

2. **Custom agent prompts:**
   ```python
   from core import PromptTemplate, format_system_prompt

   custom = PromptTemplate(
       name="custom_analysis",
       system=format_system_prompt("menu analyst", "for Mexican restaurants"),
       user_template="Analyze menu: {menu_text}"
   )

   system, user = custom.render(menu_text="Tacos, Burritos...")
   ```

3. **Workflow engine (Task 6):**
   - Agents receive PromptTemplate instances
   - Workflow passes data to `render()`

---

## Deliverable Checklist

- [x] Create `core/prompts.py` with module docstring
- [x] Implement `PromptTemplate` dataclass
  - [x] `name`, `system`, `user_template` fields
  - [x] `render(**kwargs) -> tuple[str, str]` method
  - [x] Comprehensive docstring with examples
- [x] Implement `format_system_prompt(role, context=None) -> str`
  - [x] Pattern: "You are a {role} {context}."
  - [x] Handle None/empty context
- [x] Implement `format_user_prompt(template, **kwargs) -> str`
  - [x] Wrapper around `str.format_map()`
- [x] Create pre-built templates:
  - [x] `INGREDIENT_EXTRACTION_PROMPT`
  - [x] `RECIPE_CLASSIFICATION_PROMPT`
  - [x] `INVENTORY_ITEM_SUGGESTION_PROMPT`
- [x] Add `__all__` exports to `core/prompts.py`
- [x] Update `core/__init__.py` to export all prompts utilities
- [x] Create `tests/unit/test_prompts.py`
  - [x] Test `PromptTemplate` instantiation and render (11 tests)
  - [x] Test render with missing variables raises KeyError
  - [x] Test render with extra kwargs (should work)
  - [x] Test `format_system_prompt()` with/without context (6 tests)
  - [x] Test `format_user_prompt()` substitution (6 tests)
  - [x] Test all pre-built templates render successfully (11 tests)
  - [x] Test integration scenarios (3 tests)
- [x] Run tests: `python -m pytest tests/unit/test_prompts.py -v` (37/37 passed)
- [x] Run full test suite: `python -m pytest tests/unit/ -v` (361/361 passed)

---

## Notes

- **No external dependencies:** Uses only stdlib `dataclasses` and `typing`.
- **Simple over complex:** `str.format_map()` is sufficient for MVP; no Jinja2, Mustache, etc.
- **Fail fast:** Missing variables raise `KeyError` immediately (don't use defaults or ignore).
- **Dataclass consistency:** Matches project convention (Recipe, InventoryItem, etc. are dataclasses).
- **Pre-built templates are minimal:** Agents will create custom templates as needed (Tasks 7-12).
- **Multi-line prompts:** Use `"""triple quotes"""` for readability; newlines preserved.
- **System vs user separation:** `render()` returns tuple to match `LlmProvider.generate(prompt, system=...)` signature.
- **Template naming:** Use snake_case for template variables, UPPER_CASE for pre-built constants.
- **Future enhancements (out of scope for 4.5):**
  - Template validation (check for undefined variables before render)
  - Template composition (combine multiple templates)
  - Conditional sections (if/else in templates)
  - Template versioning (track prompt changes over time)
  - Prompt optimization metrics (track which prompts work best)

---

## Time Estimate

- **Implementation:** 45-60 minutes (dataclass, helpers, 3 templates)
- **Tests:** 30-45 minutes (14+ test cases)
- **Total:** 1.5-2 hours
