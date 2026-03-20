# Subtask 17.6 — Inject restaurant_description into ConsistencyCheckAgent

## Goal

Update ConsistencyCheckAgent to receive and use `restaurant_description` in both its
per-step and final validation modes so semantic checks are restaurant-specific rather
than relying solely on the type label.

- **Prior (17.5):** ConfigurationAgent now includes `restaurant_description` in its
  system prompt; the field flows from `_load_configuration_context` → `ctx` → agent context.
- **Following (17.7):** Tests for the full description flow across all agents.

---

## What changes

| File | Action | Summary |
|------|--------|---------|
| `core/agents/consistency_check_agent.py` | Modify | Add `restaurant_description` to both system prompt field listings, both `_generate_prompt` JSON dicts, and the class docstring input shapes |

---

## Key design decisions

### `restaurant_description` arrives via `input_data`, not `context`

ConsistencyCheckAgent is called with `check_agent.run(input_data={...})` in
`configuracion.py`. It is stateless (no `store()`/`retrieve()`), so context is not
used. The field must be read from `input_data` in `_generate_prompt`.

### Include in the JSON user message, not a separate system prompt block

The agent receives all inputs as a JSON blob in the user message turn. `restaurant_description`
is added to that blob alongside `restaurant_type` — consistent with how the agent
already receives its input.

### Update system prompt field listings

Both `_PER_STEP_SYSTEM_PROMPT` and `_FINAL_SYSTEM_PROMPT` document the expected JSON
fields. The counts and field lists must be updated so the LLM knows the field exists
and can use it.

### Add semantic guidance referencing the description

Both prompts' criteria sections get a line instructing the LLM to use
`restaurant_description` for more precise semantic relevance checks when available.

### INPUT_SCHEMA stays empty

Remains `{}` intentionally — the two call shapes have incompatible keys, schema
validation is disabled by design. No change needed.

---

## Implementation steps

### 1. `_PER_STEP_SYSTEM_PROMPT` — update field listing (line 21–24)

Change "tres campos" → "cuatro campos" and add:
```
- "restaurant_description": descripción libre del restaurante (puede ser vacía)
```

### 2. `_PER_STEP_SYSTEM_PROMPT` — add guidance in Relevancia semántica (after line 74)

After the existing semantic relevance section, before `## Reglas`:
```
Usa "restaurant_description" para evaluar la relevancia semántica con mayor precisión cuando esté disponible.
```

### 3. `_FINAL_SYSTEM_PROMPT` — update field listing (line 95–100)

Change "cinco campos" → "seis campos" and add:
```
- "restaurant_description": descripción libre del restaurante (puede ser vacía)
```

### 4. `_FINAL_SYSTEM_PROMPT` — add guidance (before `## Reglas`)

Same line as step 2:
```
Usa "restaurant_description" para evaluar la consistencia semántica con mayor precisión cuando esté disponible.
```

### 5. `_generate_prompt` — per-step JSON dict (lines 195–199)

Add field after `"restaurant_type"`:
```python
"restaurant_description": input_data.get("restaurant_description", ""),
```

### 6. `_generate_prompt` — final JSON dict (lines 203–209)

Add field after `"restaurant_type"`:
```python
"restaurant_description": input_data.get("restaurant_description", ""),
```

### 7. Class docstring — update both input shape descriptions (lines 154–163)

Per-step input shape:
```
{"step": str, "entities": list[dict], "restaurant_type": str, "restaurant_description": str}
```

Final input shape:
```
{"categories": list, "families": list, "recipe_units": list,
 "inventory_units": list, "restaurant_type": str, "restaurant_description": str}
```

---

## Out of scope

- `gradio_app/sections/configuracion.py` — call sites already updated (17.4)
- `core/agents/configuration_agent.py` — already done (17.5)
- All new tests (17.7)
- `INPUT_SCHEMA` — remains `{}` intentionally

---

## Risks and open questions

### Empty description in JSON user message

When `restaurant_description` is `""` (operator skipped), the LLM receives
`"restaurant_description": ""` in the JSON. The system prompt says "puede ser vacía"
— the LLM should ignore it gracefully. No special handling needed.

---

## Deliverable checklist

### `core/agents/consistency_check_agent.py`
- [ ] `_PER_STEP_SYSTEM_PROMPT` field listing updated to include `restaurant_description`
- [ ] `_PER_STEP_SYSTEM_PROMPT` criteria section includes guidance to use description
- [ ] `_FINAL_SYSTEM_PROMPT` field listing updated to include `restaurant_description`
- [ ] `_FINAL_SYSTEM_PROMPT` criteria section includes guidance to use description
- [ ] `_generate_prompt` per-step JSON includes `restaurant_description`
- [ ] `_generate_prompt` final JSON includes `restaurant_description`
- [ ] Class docstring input shapes updated
- [ ] All existing tests pass
