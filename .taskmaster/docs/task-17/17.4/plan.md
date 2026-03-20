# Subtask 17.4 — Expose restaurant_description in _load_configuration_context

## Goal

Expose `restaurant_description` from the classification entity through
`_load_configuration_context` so every agent call site in `configuracion.py`
receives it in the context dict automatically.

- **Prior (17.3):** `clasificacion.py` now saves `restaurant_description` and
  `restaurant_description_raw` to the classification entity in DataLake on Confirm.
- **Following (17.5/17.6):** ConfigurationAgent and ConsistencyCheckAgent need
  `restaurant_description` in their context/input_data — it must be in the dict
  returned by `_load_configuration_context` first.

---

## What changes

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/configuracion.py` | Modify | Add `restaurant_description` to `_load_configuration_context` return dict and pass it in ConsistencyCheckAgent `input_data` at both call sites |

---

## Key design decisions

### Read from classification entity, not restaurant entity

Decided in 17.1. `_load_configuration_context` already loads `classification_data`
(line 135) — adding one `.get()` call is the full change. No schema changes, no new
entity loads.

### Empty string default, not None

Consistent with how `restaurant_type` and `restaurant_name` are handled in the same
function. Downstream agents check `if restaurant_description:` rather than
`if restaurant_description is not None:`.

### Extract into local variable, not inlined in call sites

`restaurant_type` is extracted from `ctx` into a local variable at line 322 before
being passed to both ConsistencyCheckAgent call sites. `restaurant_description` must
follow the same pattern — extracted once after `_load_configuration_context`, then
referenced by name in both call sites.

---

## Implementation steps

### 1. `_load_configuration_context` — read from classification entity (lines 134–146)

After the existing `standardization_level` extraction from `classification_data`, add:

```python
restaurant_description = ""
if classification_data:
    level = classification_data.get("standardization_level")
    if level is not None:
        standardization_level = level
    restaurant_description = classification_data.get("restaurant_description", "")
```

Add `"restaurant_description"` to the returned dict:

```python
return {
    "restaurant_type_id":      restaurant_type_id,
    "restaurant_type":         restaurant_type,
    "restaurant_name":         restaurant_name,
    "standardization_level":   standardization_level,
    "restaurant_description":  restaurant_description,
}
```

### 2. Extract local variable at ConsistencyCheckAgent call sites (line 322)

After the existing `restaurant_type = ctx.get("restaurant_type", "")` extraction,
add:

```python
restaurant_description = ctx.get("restaurant_description", "")
```

### 3. ConsistencyCheckAgent final-step call site — add field (lines 331–337)

```python
check_result = check_agent.run(input_data={
    "categories":             draft_cats,
    "families":               draft_fams,
    "recipe_units":           draft_ru,
    "inventory_units":        draft_iu,
    "restaurant_type":        restaurant_type,
    "restaurant_description": restaurant_description,
})
```

### 4. ConsistencyCheckAgent per-step call site — add field (lines 343–347)

```python
check_result = check_agent.run(input_data={
    "step":                   step_key,
    "entities":               current_draft,
    "restaurant_type":        restaurant_type,
    "restaurant_description": restaurant_description,
})
```

---

## Out of scope

- `core/agents/configuration_agent.py` — injecting description into ConfigurationAgent
  prompt (17.5)
- `core/agents/consistency_check_agent.py` — updating ConsistencyCheckAgent system
  prompts and `_generate_prompt` (17.6)
- All new tests (17.7)
- Draft panel / UI display changes
- Status updates to tasks.json / CLAUDE.md

---

## Risks and open questions

### [OPEN] — Second _load_configuration_context call site at line 482 and 514

There are two additional `_load_configuration_context` call sites inside the
`_make_chat_fn` closure (lines 482, 514) — these pass `ctx` to ConfigurationAgent,
not ConsistencyCheckAgent. Once `restaurant_description` is in the returned dict,
these call sites automatically receive it via `ctx` with no additional changes needed.
The ConfigurationAgent change (17.5) will consume it from there.

---

## Deliverable checklist

### `gradio_app/sections/configuracion.py`
- [ ] `_load_configuration_context` reads `restaurant_description` from `classification_data`
- [ ] `_load_configuration_context` returns `restaurant_description` in the context dict
- [ ] `restaurant_description` extracted as local variable at ConsistencyCheckAgent call sites
- [ ] ConsistencyCheckAgent final-step call site passes `restaurant_description` in `input_data`
- [ ] ConsistencyCheckAgent per-step call site passes `restaurant_description` in `input_data`
- [ ] All existing tests pass
