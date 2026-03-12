# Subtask 8.1 — ClassificationAgent

## Context

Creates `ClassificationAgent` — the only agent in the Clasificación section. It drives
the propose→preview→confirm flow through conversation. Nothing is persisted to DataLake
until the operator clicks Confirm (8.4). This subtask delivers the agent only; exports
(8.5), tests (8.6), and section UI (8.4) are handled separately.

**Prior:** Task 7 delivered `BaseAgent`, `WelcomeAgent`, and the `save_state`/`load_state`
session pattern this agent inherits directly.

**Next:** 8.2 (persistence) and 8.3 (preview component) run in parallel after this.
8.4 (section UI) imports `ClassificationAgent` and depends on it being complete.

---

## File to Create

| File | Action | Summary |
|------|--------|---------|
| `core/agents/classification_agent.py` | Create | `_ClassificationResponse` + `ClassificationAgent` |

---

## Dependencies

- `core/agents/base_agent.py` — `BaseAgent`, `store()`, `retrieve()`, `_parse_response()`
- `pydantic.BaseModel` — already a project dependency
- No prior 8.x subtasks required

---

## Design Decisions

### Decision 1: Hybrid RESPONSE_MODEL

`_ClassificationResponse` has `reply: str` (shown to operator) plus
`standardization_level: int | None` and `sections: dict | None` (silently merged into
draft). One LLM call per turn produces both outputs.

### Decision 2: Incremental _data_store merge

`_process_response()` skips `None` fields entirely. For `sections` specifically, it
deep-merges at the key level — never replaces the whole dict. This preserves section
data from prior turns when the LLM only returns partial sections on a given turn.

### Decision 3: Draft injected into system prompt

On every turn, the current `_data_store` content is appended to the system prompt as
JSON. The agent sees what has already been captured and avoids re-asking answered
questions.

### Decision 4: No JSON format instructions in system prompt

`RESPONSE_MODEL is not None` automatically enables `structured_output=True` at the
provider level. The system prompt describes behavior only, not output format.

### Decision 5: Two-phase conversation structure

The system prompt guides the agent through two phases:
- Phase 1 (2–3 broad questions) — diagnoses the standardization level
- Phase 2 (4 focused questions) — confirms `has_data` for each section

All 4 sections must be resolved before the agent proposes a final classification.
The agent may blend the two phases naturally rather than treating them as explicit rounds.

### Decision 6: Impatient operator fallback

If the operator signals they want to skip ahead ("just set it up for me"), the agent
proposes Level 1 with all sections `has_data: false` as a safe default and communicates
this is a starting point they can correct later. This ensures the confirm button always
becomes reachable.

---

## _ClassificationResponse

```python
from pydantic import BaseModel

class _ClassificationResponse(BaseModel):
    reply: str
    standardization_level: int | None = None
    sections: dict | None = None
```

---

## ClassificationAgent Schema

```python
INPUT_SCHEMA = {
    "user_message": "A message from the restaurant operator.",
}
OUTPUT_SCHEMA = {
    "reply":                 "Conversational response shown to the operator.",
    "standardization_level": "Diagnosed level (1/2/3) or None if not yet determined.",
    "sections":              "Dict of section has_data flags or None.",
    "raw_response":          "Full LLM response string.",
}
RESPONSE_MODEL = _ClassificationResponse
```

---

## System Prompt Guidance

The `_SYSTEM_PROMPT` constant (module-level) must cover:

**Role:** Diagnose the operator's standardization level and determine which sections
have existing documentation.

**Standardization levels:**
- Level 1 — Everything in the operator's head. No documentation. Use all base templates.
- Level 2 — Partially documented. Has some Excel, notes, photos, or partial recipes. Use
  templates where documentation is missing.
- Level 3 — Structured operation. Most categories, recipes, and inventory documented.
  Import and normalize existing information.

**Phase 1 — Level diagnosis questions (2–3, use judgment on which apply):**
- How many years has the restaurant been operating?
- On a scale of 1–10, how standardized do you feel your operation is?
- Can you leave for a weekend without the operation falling apart?
- When a new employee joins, how do they learn the job?

**Phase 2 — Section documentation check (all 4 required):**
The agent must determine `has_data` for each section before proposing a final
classification. It may blend these questions into the conversation naturally:
- `recipe_categories`: Do you have your recipe categories defined? (e.g. Entradas, Platos fuertes)
- `inventory_families`: Do you have inventory families defined? (e.g. Carnes, Lácteos)
- `recipes`: Do you have recipes written down with ingredients and quantities?
- `inventory`: Do you have an inventory list with units and suppliers?

**Impatient operator fallback:**
If the operator signals they want to skip ahead or says something like "just set it
up for me" or "I don't know, just start", the agent must:
1. Propose Level 1 with all sections as `has_data: false`
2. Explain this is a safe starting point — all templates will be available
3. Invite them to correct it if something seems wrong

**Communication rules:**
- Always in Spanish
- 2–4 sentences per response
- Propose a level as soon as confident — do not wait for every possible question
- Do not include raw JSON in the `reply` field

---

## _generate_prompt() Implementation Notes

```python
def _generate_prompt(self, input_data, context) -> tuple[str, str]:
    system = _SYSTEM_PROMPT

    # 1. Inject restaurant context if available
    context_lines = []
    if context.get("restaurant_name"):
        context_lines.append(f"El restaurante se llama {context['restaurant_name']}.")
    if context.get("restaurant_type"):
        context_lines.append(f"Es un restaurante de tipo {context['restaurant_type']}.")
    if context_lines:
        system = system + "\n\n## Contexto del restaurante\n" + "\n".join(context_lines)

    # 2. Inject current draft so agent knows what's already captured
    current_draft = {}
    level = self.retrieve("standardization_level")
    sections = self.retrieve("sections")
    if level is not None:
        current_draft["standardization_level"] = level
    if sections is not None:
        current_draft["sections"] = sections
    if current_draft:
        system = (
            system
            + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
            + json.dumps(current_draft, ensure_ascii=False, indent=2)
        )

    return system, input_data["user_message"]
```

---

## _process_response() Implementation Notes

```python
def _process_response(self, response: str) -> dict[str, Any]:
    data = self._parse_response(response)

    # standardization_level: simple store, only if non-None
    level = data.get("standardization_level")
    if level is not None:
        self.store("standardization_level", level)

    # sections: deep-merge at key level — never replace whole dict
    sections = data.get("sections")
    if sections is not None:
        existing = self.retrieve("sections") or {}
        existing.update(sections)
        self.store("sections", existing)

    return {
        "reply":                 data.get("reply", ""),
        "standardization_level": data.get("standardization_level"),
        "sections":              data.get("sections"),
        "raw_response":          response,
    }
```

Key constraint: `self.store("sections", new_sections)` directly would wipe prior turns.
Always use the deep-merge pattern above.

---

## Plan Completeness

| Category | Status |
|----------|--------|
| Unit tests (mocked) | Covered in subtask 8.6 |
| Live tests | Covered in subtask 8.6 (guarded by `ANTHROPIC_API_KEY`) |
| Error handling | `_parse_response` returns `{}` on malformed JSON; `data.get("reply", "")` handles missing reply gracefully |
| Re-exports | Covered in subtask 8.5 |
| Status updates | Covered in subtask 8.7 |
| Inline docstrings | Must be included on `_ClassificationResponse` and `ClassificationAgent` |

---

## Risks and Open Questions

### [OPEN] — sections type validation
**Problem:** `sections: dict | None` accepts any structure from the LLM.
**Impact:** Malformed sections silently default to `has_data: false` in `_make_confirm_fn`.
**Suggested action:** Guard in 8.4's `_make_confirm_fn` with explicit `.get("has_data", False)` per section key. No change needed in 8.1.

### [OPEN] — Level 1 fallback wording
**Problem:** The exact phrasing the agent uses to signal the impatient fallback is not
defined — the system prompt author decides at implementation time.
**Impact:** Inconsistent tone if not aligned with the rest of Zenet's voice.
**Suggested action:** Use the same warm, non-judgmental tone as WelcomeAgent's system prompt.

### [OPEN] — standardization_level range not validated
**Source:** Validation of subtask 8.1
**Problem:** `_ClassificationResponse` declares `standardization_level: int | None` with no range constraint. The LLM could return 0, 4, or any integer. No Pydantic validator or guard in `_process_response()` enforces the {1, 2, 3} set.
**Impact:** 8.3's preview renderer maps level → "Nivel 1/2/3" label. An out-of-range value produces a blank or broken label. The wrong level would also be persisted to SQLite via confirm_fn.
**Suggested action:** Add a Pydantic `field_validator` in `_ClassificationResponse` clamping `standardization_level` to `{1, 2, 3}` or `None`, OR handle unknown values gracefully in 8.3's Markdown renderer. Address before implementing 8.3.

---

## Deliverable Checklist

- [ ] `_ClassificationResponse` Pydantic model with `reply`, `standardization_level`, `sections`
- [ ] `ClassificationAgent` with correct `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_generate_prompt()` injects restaurant context + current `_data_store` draft
- [ ] System prompt includes Phase 1 broad questions (level diagnosis)
- [ ] System prompt includes Phase 2 section-by-section documentation check (all 4 sections)
- [ ] System prompt includes impatient operator fallback (Level 1 default)
- [ ] `_process_response()` skips `None` fields
- [ ] `_process_response()` deep-merges `sections` dict (not simple store)
