# Subtask 17.3 — Update clasificacion.py Confirm Flow

## Goal

Wire `restaurant_description` and `restaurant_description_raw` from ClassificationAgent's
`_data_store` through the Gradio confirm flow so both fields are persisted to the
classification entity in DataLake when the operator clicks Confirm.

- **Prior (17.2):** ClassificationAgent now stores `restaurant_description` and
  `restaurant_description_raw` in `_data_store` after the operator answers the description
  question.
- **Following (17.4):** `_load_configuration_context` in `configuracion.py` will read
  `restaurant_description` from the classification entity — it must be saved there first.

---

## What changes

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/clasificacion.py` | Modify | Add description fields to `draft_dict` in `_make_chat_fn`; include them in the classification entity dict in `_make_confirm_fn` |

---

## Key design decisions

### Pass description through `draft_dict`, not a second `load_state` call

`_make_chat_fn` already calls `agent.retrieve("standardization_level")` after each turn.
Adding `agent.retrieve("restaurant_description")` and `agent.retrieve("restaurant_description_raw")`
to `draft_dict` means `confirm_fn` can read both from Gradio State — no need to reload
agent state inside `confirm_fn`, which would require passing `provider` and reconstructing
the agent closure.

### Store in classification entity, not restaurant entity

Decided in 17.1. The `restaurant` entity uses typed SQLite columns that silently drop
unknown keys. The `classification` entity uses a JSON blob (`data TEXT NOT NULL`) —
any keys added to the dict are preserved automatically. Zero schema changes needed.

### Description is optional — confirm is not gated on it

`standardization_level` is required and already gates the Confirm button. Description
is intentional enrichment — the agent accepts null if the operator skips. Blocking Confirm
on description would require an extra `description_asked` flag for optional data.
Stay as is: Confirm activates on level, saves whatever description is in `_data_store`.

---

## Implementation steps

### 1. `_make_chat_fn` — extend `draft_dict` (line 55–57)

After the existing `level = agent.retrieve("standardization_level")` call, retrieve both
description fields and include them in `draft_dict`:

```python
level = agent.retrieve("standardization_level")
description = agent.retrieve("restaurant_description")
description_raw = agent.retrieve("restaurant_description_raw")
draft_dict = {"standardization_level": level} if level is not None else {}
if description is not None:
    draft_dict["restaurant_description"] = description
if description_raw is not None:
    draft_dict["restaurant_description_raw"] = description_raw
```

### 2. `_make_confirm_fn` — save description to classification entity (line 70)

Read both fields from `draft_dict` and include them in the classification entity dict.
Fields are optional — save whatever is present:

```python
classification_dict = {"standardization_level": level}
description = (draft_dict or {}).get("restaurant_description")
description_raw = (draft_dict or {}).get("restaurant_description_raw")
if description is not None:
    classification_dict["restaurant_description"] = description
if description_raw is not None:
    classification_dict["restaurant_description_raw"] = description_raw
data_lake.save_entity("classification", entity_id, classification_dict)
```

---

## End-to-end data flow

```
Turn N (description answered)
  → ClassificationAgent._process_response()
      → _data_store["restaurant_description"] = enriched profile
      → _data_store["restaurant_description_raw"] = operator's exact words

Next chat_fn call (after turn N)
  → agent.retrieve("restaurant_description") → draft_dict["restaurant_description"]
  → Gradio State draft_state updated

Operator clicks Confirm
  → confirm_fn(draft_dict, session_id)
      → classification_dict = {
            "standardization_level": 1,
            "restaurant_description": "Taquería familiar en la colonia Roma...",
            "restaurant_description_raw": "tacos y quesadillas, mostrador, como 30 sillas"
        }
      → data_lake.save_entity("classification", entity_id, classification_dict)
          → SQLite: UPDATE classification SET data = '{"standardization_level": 1, ...}'
```

---

## Out of scope

- `components.py` / `_format_draft` — draft panel will not display `restaurant_description`
  (UI display of description in the preview panel is deferred)
- `gradio_app/sections/configuracion.py` — loading description from classification entity (17.4)
- `core/agents/configuration_agent.py` — injecting description into prompts (17.5)
- `core/agents/consistency_check_agent.py` — injecting description into prompts (17.6)
- All new tests (17.7)
- Status updates to tasks.json / CLAUDE.md

---

## Risks and open questions

### [OPEN] — Draft panel does not display restaurant_description

`_format_draft` in `components.py` only reads `standardization_level` from `draft_dict`.
Adding `restaurant_description` to `draft_dict` is sufficient for `confirm_fn` to save it,
but the operator has no visual confirmation in the preview panel that their description
was captured before confirming.

Impact: minor UX gap — operator cannot verify the captured description before confirming.
Suggested action: decide whether to update `_format_draft` to render the description.
Not a blocker — the save path works regardless.

### [OPEN] — Draft panel does not show restaurant_description to operator
**Source:** Validation of subtask 17.3
**Problem:** `_format_draft` in `components.py` only reads `standardization_level`. `restaurant_description` will be in `draft_dict` but not rendered in the preview panel.
**Impact:** Operator has no visual confirmation that their description was captured before clicking Confirm.
**Suggested action:** Decide in 17.3 or defer: update `_format_draft` to render description below the level panel. Small change, big UX improvement.

### [OPEN] — Operator skip-process path (carried from 17.2)

The "Operador que quiere saltarse el proceso" section in `_SYSTEM_PROMPT` does not mention
the description question. Skip-path operators may still get asked for a description.

Impact: inconsistent UX for operators who skip classification.
Suggested action: add to that prompt section in `classification_agent.py`:
"Si el operador quiere saltarse, no preguntes por la descripción — deja description y
description_raw en null." Apply as follow-up polish, not a blocker for 17.3.

---

## Deliverable checklist

### `gradio_app/sections/clasificacion.py`
- [x] `_make_chat_fn` includes `restaurant_description` in `draft_dict`
- [x] `_make_chat_fn` includes `restaurant_description_raw` in `draft_dict`
- [x] `_make_confirm_fn` reads `restaurant_description` from `draft_dict`
- [x] `_make_confirm_fn` reads `restaurant_description_raw` from `draft_dict`
- [x] `_make_confirm_fn` saves both fields to classification entity in DataLake
- [x] Description fields are optional — confirm still works when operator skipped description
- [x] All existing tests pass (19 passed in 20.99s)
