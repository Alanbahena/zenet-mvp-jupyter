# Subtask 8.1 — ClassificationAgent

## Context

Creates `ClassificationAgent` — the only agent in the Clasificación section. It diagnoses
the operator's standardization level (1–3) through a short conversation. Nothing is persisted
to DataLake until the operator clicks Confirm (8.4). This subtask delivers the agent only;
exports (8.5), tests (8.6), and section UI (8.4) are handled separately.

The diagnosed level is stored in `_data_store` and later written to DataLake as
`{"standardization_level": 2}`. Tasks 9–12 load this value to calibrate their agents'
tone, suggestions, and approach for each section.

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

### Decision 1: Hybrid RESPONSE_MODEL — level only

`_ClassificationResponse` has `reply: str` (shown to operator) plus
`standardization_level: int | None`. One LLM call per turn produces both outputs.
Per-section `has_data` questions are handled by each section's own agent in Tasks 9–12.

### Decision 2: Level stored incrementally

`_process_response()` stores `standardization_level` only when non-None. Early turns
may return `None` — the stored value from a prior turn is preserved.

### Decision 3: Draft injected into system prompt

On every turn, the current `standardization_level` from `_data_store` is appended to
the system prompt. The agent knows what has already been captured and avoids re-proposing.

### Decision 4: No JSON format instructions in system prompt

`RESPONSE_MODEL is not None` automatically enables `structured_output=True` at the
provider level. The system prompt describes behavior only, not output format.

### Decision 5: Level diagnosis only (no per-section questions)

The agent asks 2–3 broad questions to diagnose the standardization level. It does not
ask about documentation per section — that happens contextually in each section (Tasks 9–12).

### Decision 6: Impatient operator fallback

If the operator signals they want to skip ahead, the agent proposes Level 1 as a safe
default and communicates that Zenet will guide them step by step from base templates.

---

## _ClassificationResponse

```python
from pydantic import BaseModel, field_validator

class _ClassificationResponse(BaseModel):
    reply: str
    standardization_level: int | None = None

    @field_validator("standardization_level")
    @classmethod
    def validate_level(cls, v: int | None) -> int | None:
        if v is not None and v not in {1, 2, 3}:
            return None
        return v
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
    "raw_response":          "Full LLM response string.",
}
RESPONSE_MODEL = _ClassificationResponse
```

---

## System Prompt Guidance

The `_SYSTEM_PROMPT` constant (module-level) must cover:

**Role:** Diagnose the operator's standardization level. This level will calibrate
Zenet's suggestions and approach in every section of the pipeline.

**Standardization levels:**
- Level 1 — Everything in the operator's head. No documentation. Zenet builds from base templates and guides each step.
- Level 2 — Partially documented. Has some Excel, notes, photos, or partial recipes. Zenet uses what exists and fills gaps with templates.
- Level 3 — Structured operation. Most categories, recipes, and inventory documented. Zenet imports and normalizes existing information.

**Diagnosis questions (2–3, use judgment on which apply):**
- How many years has the restaurant been operating?
- On a scale of 1–10, how standardized do you feel your operation is?
- Can you leave for a weekend without the operation falling apart?
- When a new employee joins, how do they learn the job?

**Impatient operator fallback:**
If the operator signals they want to skip ahead or says something like "just set it
up for me" or "I don't know, just start", the agent must:
1. Propose Level 1 as a safe starting point
2. Explain that Zenet will guide them step by step from base templates
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

    # 2. Inject current level if already captured
    level = self.retrieve("standardization_level")
    if level is not None:
        system = (
            system
            + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
            + json.dumps({"standardization_level": level}, ensure_ascii=False)
        )

    return system, input_data["user_message"]
```

---

## _process_response() Implementation Notes

```python
def _process_response(self, response: str) -> dict[str, Any]:
    data = self._parse_response(response)

    # standardization_level: store only if non-None
    level = data.get("standardization_level")
    if level is not None:
        self.store("standardization_level", level)

    return {
        "reply":                 data.get("reply", ""),
        "standardization_level": data.get("standardization_level"),
        "raw_response":          response,
    }
```

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

### [OPEN] — Level 1 fallback wording
**Problem:** The exact phrasing the agent uses to signal the impatient fallback is not
defined — the system prompt author decides at implementation time.
**Impact:** Inconsistent tone if not aligned with the rest of Zenet's voice.
**Suggested action:** Use the same warm, non-judgmental tone as WelcomeAgent's system prompt.

---

## Deliverable Checklist

- [ ] `_ClassificationResponse` Pydantic model with `reply` and `standardization_level`
- [ ] `field_validator` clamping `standardization_level` to `{1, 2, 3}` or `None`
- [ ] `ClassificationAgent` with correct `INPUT_SCHEMA`, `OUTPUT_SCHEMA`, `RESPONSE_MODEL`
- [ ] `_generate_prompt()` injects restaurant context + current level from `_data_store`
- [ ] System prompt covers level diagnosis questions (2–3 broad questions)
- [ ] System prompt covers impatient operator fallback (Level 1 default)
- [ ] `_process_response()` stores level only if non-None
- [ ] No `sections` field anywhere in the agent
