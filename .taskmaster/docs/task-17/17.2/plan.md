# Subtask 17.2 — Update ClassificationAgent with Description Question

## Goal

Add a restaurant description question to ClassificationAgent so it captures a free-text
profile after diagnosing the standardization level. The agent enriches the operator's raw
input into a structured profile for downstream agent consumption.

- **Prior (17.1):** Determined storage target — classification entity (JSON blob).
- **Following (17.3):** Needs `restaurant_description` and `restaurant_description_raw`
  in `agent._data_store` so `confirm_fn` can save them to DataLake.

---

## What changes

| File | Action | Summary |
|------|--------|---------|
| `core/agents/classification_agent.py` | Modify | Add description fields to response model, prompt, `_process_response`, and `OUTPUT_SCHEMA` |

---

## Key design decisions

### Two-field approach (enriched + raw)

- `restaurant_description`: agent-enriched profile, structured and complete, optimized
  for downstream agent readability. Synthesized from conversation + injected context.
- `restaurant_description_raw`: operator's exact words, unmodified — preserved for
  transparency and auditability.

### No-hallucination rule

The agent may ONLY use:
1. What the operator said during the conversation (all turns)
2. The injected context (restaurant name, restaurant type)

It must NOT invent, assume, or infer data not explicitly stated. If the operator provides
sparse input (e.g. "tacos"), the enriched description stays short and grounded.

### Trigger timing

The description question is triggered when `standardization_level` is non-None in
`_data_store`. The draft injection block includes `restaurant_description` when present,
signaling to the LLM that the question was already asked — prevents re-asking.

### Optional field

The operator can skip. The agent accepts null and does not insist — one question only.

---

## Implementation steps

### 1. `_ClassificationResponse` (Pydantic model)

Added two optional fields:
```python
description: str | None = None
description_raw: str | None = None
```

No validator needed — free text, any value is valid.

### 2. `_SYSTEM_PROMPT` — New section `## Descripción del restaurante`

Inserted before `## Reglas de comunicación`. Instructions:
- Ask after `standardization_level` is diagnosed (non-null)
- Operator describes restaurant briefly (cuisine, service style, size, zone)
- Agent synthesizes enriched profile in `description` field
- Agent copies operator's exact words to `description_raw` field
- **REGLA ABSOLUTA**: only use explicitly provided or injected information
- If operator declines, leave both fields null. Do not insist.

### 3. `_SYSTEM_PROMPT` — Updated `## Formato de respuesta`

Changed from 2 fields to 4:
- `"reply"` — conversational response
- `"standardization_level"` — diagnosed level or null
- `"description"` — enriched restaurant profile or null
- `"description_raw"` — operator's exact words or null

### 4. `_generate_prompt` — Draft injection

Updated to include `restaurant_description` in the draft dict:
```python
level = self.retrieve("standardization_level")
description = self.retrieve("restaurant_description")
draft: dict[str, Any] = {}
if level is not None:
    draft["standardization_level"] = level
if description is not None:
    draft["restaurant_description"] = description
if draft:
    system = system + "\n\n## Borrador actual...\n" + json.dumps(draft)
```

This signals to the LLM: if `restaurant_description` is already in the draft, the
question was already asked — don't re-ask.

### 5. `_process_response` — Store and return both values

```python
description = data.get("description")
if description is not None:
    self.store("restaurant_description", description)
description_raw = data.get("description_raw")
if description_raw is not None:
    self.store("restaurant_description_raw", description_raw)
```

Return dict now includes `restaurant_description` and `restaurant_description_raw`.

### 6. `OUTPUT_SCHEMA` and class docstring

Updated to document all 5 output fields.

---

## Field name mapping

| Pydantic field (`_ClassificationResponse`) | `_data_store` key | `OUTPUT_SCHEMA` / return dict key |
|--------------------------------------------|-------------------|-----------------------------------|
| `description` | `restaurant_description` | `restaurant_description` |
| `description_raw` | `restaurant_description_raw` | `restaurant_description_raw` |
| `standardization_level` | `standardization_level` | `standardization_level` |

The Pydantic field names match the LLM JSON output. The `_data_store` and return dict
keys use the `restaurant_` prefix to be explicit about what they describe.

---

## Test results

All 19 existing tests pass (16 mocked + 3 live):
```
19 passed in 21.70s
```

New fields are optional (`None` default) — existing mocked responses that only return
`reply` + `standardization_level` continue to work without modification.

---

## Out of scope

- `clasificacion.py` confirm flow changes (17.3)
- `configuracion.py` context loader changes (17.4)
- ConfigurationAgent / ConsistencyCheckAgent prompt changes (17.5, 17.6)
- New tests for description flow (17.7)

---

## Deliverable checklist

### `core/agents/classification_agent.py`
- [x] `_ClassificationResponse` includes `description` and `description_raw` fields
- [x] `_SYSTEM_PROMPT` includes `## Descripción del restaurante` section
- [x] `_SYSTEM_PROMPT` includes no-hallucination rule (REGLA ABSOLUTA)
- [x] `_SYSTEM_PROMPT` format section lists all 4 JSON fields
- [x] `_generate_prompt` draft injection includes `restaurant_description`
- [x] `_process_response` stores `restaurant_description` in `_data_store`
- [x] `_process_response` stores `restaurant_description_raw` in `_data_store`
- [x] `_process_response` returns both in result dict
- [x] `OUTPUT_SCHEMA` includes `restaurant_description` and `restaurant_description_raw`
- [x] Class docstring updated with new output fields
- [x] Module docstring updated
- [x] All 19 existing tests pass
