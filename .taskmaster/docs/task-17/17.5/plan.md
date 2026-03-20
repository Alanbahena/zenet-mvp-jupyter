# Subtask 17.5 — Inject restaurant_description into ConfigurationAgent

## Goal

Inject `restaurant_description` into ConfigurationAgent's system prompt so the agent
makes restaurant-specific suggestions instead of generic ones based only on type label.

- **Prior (17.4):** `_load_configuration_context` now returns `restaurant_description`
  in the context dict; it flows to ConfigurationAgent via `ctx` in `configuracion.py`.
- **Following (17.6):** ConsistencyCheckAgent needs the same field — it receives it via
  `input_data`, not `context`, so its change is separate.

---

## What changes

| File | Action | Summary |
|------|--------|---------|
| `core/agents/configuration_agent.py` | Modify | Extract `restaurant_description` from context and append it to `context_parts` in `_generate_prompt` |

---

## Key design decisions

### Conditional append, not unconditional

Same pattern as `restaurant_name` and `restaurant_type` (lines 224–227): only append
if the value is truthy. Empty string when operator skipped → line is omitted → prompt
identical to pre-17 behavior.

### Single line in context_parts

Format matches the parent plan: `"Descripción del restaurante: {restaurant_description}"`.
Keeps the context block consistent with existing single-line entries.

### Placement: after restaurant_type, before standardization_level

Groups identity fields together (`restaurant_name`, `restaurant_type`,
`restaurant_description`) before operational fields (`standardization_level`,
`current_step`).

---

## Implementation steps

### 1. Extract from context (after line 202)

After the existing context extractions:

```python
restaurant_description: str = context.get("restaurant_description", "")
```

### 2. Append to context_parts (after line 227)

After the `if restaurant_type:` block, before the `standardization_level` append:

```python
if restaurant_description:
    context_parts.append(f"Descripción del restaurante: {restaurant_description}")
```

Current context block order after this change:
```
## Contexto del operador
Restaurante: {name}           ← existing
Tipo: {type}                  ← existing
Descripción del restaurante: {description}  ← new
Nivel de estandarización: {level}  ← existing
Paso actual: ...              ← existing
```

---

## Out of scope

- `core/agents/consistency_check_agent.py` — separate agent, separate subtask (17.6)
- `gradio_app/sections/configuracion.py` — already done (17.4)
- `INPUT_SCHEMA` update — `restaurant_description` arrives via `context`, not
  `input_data`, so no schema change needed
- All new tests (17.7)

---

## Risks and open questions

None identified. The change is a two-line addition following an established pattern
already present in the file. The `context` parameter already carries `restaurant_description`
as of 17.4.

---

## Deliverable checklist

### `core/agents/configuration_agent.py`
- [x] `restaurant_description` extracted from context in `_generate_prompt`
- [x] `restaurant_description` appended to `context_parts` when non-empty
- [x] Placement: between `Tipo` and `Nivel de estandarización` lines
- [x] Empty/skipped description produces identical prompt to pre-17 behavior
- [x] All existing tests pass (532 passed in 71.63s)
