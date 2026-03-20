# Subtask 17.8 — Documentation updates for Task 17

## Goal

Update all architecture docs and CLAUDE.md to reflect the `restaurant_description` field
added across the pipeline in subtasks 17.1–17.7. Ensures Tasks 10–12 implementers have
accurate docs before Alineamiento begins.

**Builds on:** 17.7 — mocked tests done; implementation complete and verified.
**Required by:** Task 10 (Alineamiento) — must start with current docs.

---

## Dependencies

- Subtasks 17.1–17.7 all `done`
- No new packages or env vars needed

---

## Key design decisions

**Where `restaurant_description` lives (from 17.1):**
Stored in the `classification` entity's JSON blob alongside `standardization_level`.
NOT a column on the `restaurant` SQLite table (typed columns would require schema migration).
This means the `Restaurant` dataclass was NOT modified — document accordingly.

**No-hallucination rule (from 17.2):**
The enriched `description` field in `_ClassificationResponse` may only use information
the operator explicitly provided or that was injected as context. Must be documented.

**Two-field pattern (from 17.2):**
Two distinct namespaces:
- LLM JSON response fields: `description` (enriched profile) and `description_raw` (operator's exact words)
- `_data_store` and `OUTPUT_SCHEMA` keys: `restaurant_description` and `restaurant_description_raw`

`_process_response()` reads `description`/`description_raw` from the LLM response and stores
them under the `restaurant_*` prefixed keys. Both stored in `_data_store` and persisted to
the classification entity at confirm.

---

## Files to modify

| File | Action | Summary |
|------|--------|---------|
| `CLAUDE.md` | Modify | Update Task 17 status to `done` in task status table |
| `docs/Architecture/sections/clasificacion.md` | Modify | Document description question flow, updated OUTPUT_SCHEMA, updated entity schema |
| `docs/Architecture/sections/configuracion.md` | Modify | Document `restaurant_description` in context loader, ConfigurationAgent prompt, and ConsistencyCheckAgent input schemas |
| `docs/Architecture/architecture-data-model.md` | Modify | Add note that `restaurant_description` is in classification JSON blob, not a Restaurant column |
| `docs/Architecture/architecture-agent-framework.md` | Modify | Document multi-turn agent context threading pattern |

---

## Implementation steps

### Step 1 — CLAUDE.md

In the task status table, change Task 17 row:
- `pending` → `done`

### Step 2 — sections/clasificacion.md

**Section 3 (ClassificationAgent) — OUTPUT_SCHEMA table:**
Add two fields:
- `restaurant_description: str | None` — agent-enriched restaurant profile (structured for downstream agents)
- `restaurant_description_raw: str | None` — operator's exact words

Add note: the agent asks for description after `standardization_level` is diagnosed (non-None).
LLM JSON fields are `description`/`description_raw`; stored and surfaced as
`restaurant_description`/`restaurant_description_raw`. No-hallucination rule: only information
the operator explicitly provided or context-injected data may be used.

**Section 5 (Entity Stored) — schema:**
Update from:
```
{"standardization_level": 1 | 2 | 3}
```
To:
```
{
  "standardization_level": 1 | 2 | 3,
  "restaurant_description": str | None,
  "restaurant_description_raw": str | None
}
```

**New Section 8 — Restaurant Description Flow:**
Document:
- Trigger: agent asks for description once `standardization_level` is non-None in `_data_store`
- One question only — agent does not repeat if operator skips or says they don't know
- Skip-path: if operator skips classification, description stays null (agent does not ask)
- Both fields stored in `_data_store` via `agent.store()`; persisted at confirm in `_make_confirm_fn`

### Step 3 — sections/configuracion.md

**Section 4 (ConsistencyCheckAgent) — per-step input schema:**
Update from:
```
{"step": str, "entities": list[dict], "restaurant_type": str}
```
To:
```
{"step": str, "entities": list[dict], "restaurant_type": str, "restaurant_description": str}
```

**Section 4 (ConsistencyCheckAgent) — final check input schema:**
Update from:
```
{"categories": list, "families": list, "recipe_units": list, "inventory_units": list, "restaurant_type": str}
```
To:
```
{"categories": list, "families": list, "recipe_units": list, "inventory_units": list,
 "restaurant_type": str, "restaurant_description": str}
```

**Section 6 (_load_configuration_context) — returned dict:**
Add `restaurant_description` to the documented return value:
- Source: `classification` entity → `classification_data.get("restaurant_description", "")`
- Defaults to `""` if not present (operator skipped or used older session)

**Section 3 (ConfigurationAgent) — context block:**
Add `restaurant_description` to the documented context parts injected into `_generate_prompt`.
Rendered as: `"Descripción del restaurante: {value}"` — only included if non-empty.

### Step 4 — architecture-data-model.md

Add a note under the `Restaurant` entity (or in a dedicated callout) clarifying:
- `restaurant_description` is NOT a column on the `restaurant` SQLite table
- It is stored in the `classification` entity's JSON `data` blob alongside `standardization_level`
- Reason: `restaurant` uses typed SQLite columns; adding a new column requires schema migration.
  The `classification` entity uses a generic JSON blob — zero changes to `schema.py` needed.
- Cross-reference: see `sections/clasificacion.md` Section 5 for full classification entity schema.

### Step 5 — architecture-agent-framework.md

Add a new section: **Cross-section context threading pattern** (introduced in Task 17).

Document the pattern:
```
ClassificationAgent._data_store
    │ agent.store("restaurant_description", value)
    ▼
_make_confirm_fn (clasificacion.py)
    │ data_lake.save_entity("classification", id, {"restaurant_description": value, ...})
    ▼
_load_configuration_context (configuracion.py)
    │ classification_data.get("restaurant_description", "")
    ▼
ConfigurationAgent._generate_prompt(context)
ConsistencyCheckAgent.run(input_data)
    │ context["restaurant_description"] / input_data["restaurant_description"]
    ▼
Agent system prompt / user message JSON
```

Key properties:
- One-directional: flows from earlier sections to later ones via DataLake
- Single load point: `_load_configuration_context` is the only place the field is read from storage
- Forward-compatible: Tasks 10–12 agents receive `restaurant_description` automatically if they
  use the same context loader pattern
- No agent-to-agent coupling: agents communicate only through DataLake, never directly

---

## Out of scope

- Code changes of any kind
- Tasks 10–12 agent prompt docs (not yet implemented)
- `architecture-persistence.md` or `architecture-gradio-and-langgraph.md` updates
- `sections/bienvenida.md` updates (Restaurant dataclass unchanged)
- Validation or constraints on the description content

---

## Risks and open questions

- **tasks.json naming:** The subtask description says "Document `restaurant.description` field"
  but the field lives in the `classification` entity, not the `restaurant` entity. Document it
  correctly (classification blob) and do not add it as a `Restaurant` dataclass field.

### [OPEN] — Section 8 scope: what `description_raw` is used for downstream
**Source:** Validation of subtask 17.8
**Problem:** The new Section 8 in clasificacion.md will document both `restaurant_description`
and `restaurant_description_raw` as persisted to the classification entity. But only
`restaurant_description` is loaded by `_load_configuration_context` and passed to downstream
agents. `restaurant_description_raw` is stored but never read downstream. The doc does not
explain this asymmetry.
**Impact:** Task 10–12 implementers may expect `restaurant_description_raw` to be available
in agent context and look for it — it won't be there.
**Suggested action:** Add one sentence to Section 8: "`restaurant_description_raw` is
persisted for transparency only; only `restaurant_description` is loaded by
`_load_configuration_context` and injected into downstream agents."

---

## Deliverable checklist

### `CLAUDE.md`
- [x] Task 17 status updated to `done`

### `docs/Architecture/sections/clasificacion.md`
- [x] Section 3: OUTPUT_SCHEMA includes `restaurant_description` and `restaurant_description_raw` fields
- [x] Section 3: Description question trigger and no-hallucination rule documented
- [x] Section 5: Entity schema includes `restaurant_description` and `restaurant_description_raw`
- [x] Section 8 (new): Restaurant description flow documented end-to-end

### `docs/Architecture/sections/configuracion.md`
- [x] Section 3: `restaurant_description` in ConfigurationAgent context block documented
- [x] Section 4: Per-step ConsistencyCheckAgent input schema includes `restaurant_description`
- [x] Section 4: Final check input schema includes `restaurant_description`
- [x] Section 6: `_load_configuration_context` return dict includes `restaurant_description`

### `docs/Architecture/architecture-data-model.md`
- [x] Note added: `restaurant_description` lives in classification JSON blob, not restaurant table

### `docs/Architecture/architecture-agent-framework.md`
- [x] Cross-section context threading pattern documented with flow diagram
