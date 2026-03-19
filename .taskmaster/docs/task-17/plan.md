# Task 17 — Restaurant Profile Enrichment

## Why this task exists

Right now every downstream agent (ConfigurationAgent, ConsistencyCheckAgent, and future
Alineamiento/Estructura agents) only knows the restaurant *type label* (Casual, Gourmet, etc.)
and the standardization level. This is too thin for meaningful suggestions.

A free-text restaurant description captured early — "Restaurante mexicano de comida casera,
enfocado en comidas corridas, 40 cubiertos, zona residencial" — gives every agent richer
context to:
- Suggest entity names that match the actual cuisine (e.g. "Chiles y especias" instead of
  generic "Condimentos")
- Flag semantic mismatches more accurately (a taquería doesn't need a "Mariscos" family)
- Propose categories, families, and units that fit the real operation

**Must be done before Task 10 (Alineamiento).** If added after the full pipeline is built,
every agent system prompt across Tasks 10–12 would need to be retrofitted.

---

## Dependency

- Task 9 done (ConfigurationAgent, ConsistencyCheckAgent, configuracion.py all built)
- Task 8 done (ClassificationAgent and clasificacion.py built)
- No new packages or env vars required

---

## Scope

### What changes

| File | Action | Summary |
|------|--------|---------|
| `core/agents/classification_agent.py` | Modify | Add follow-up question after standardization level is diagnosed — ask for a short free-text description of the restaurant |
| `core/storage/persistence.py` / `schema.py` | Modify (if needed) | Ensure the restaurant entity supports a `description` field |
| `gradio_app/sections/clasificacion.py` | Modify | Save the description to the restaurant entity in DataLake when confirmed |
| `gradio_app/sections/configuracion.py` | Modify | Load `restaurant_description` in `_load_configuration_context` and expose it in the context dict |
| `core/agents/configuration_agent.py` | Modify | Inject `restaurant_description` into the operator context block in `_generate_prompt` |
| `core/agents/consistency_check_agent.py` | Modify | Inject `restaurant_description` into both `_PER_STEP_SYSTEM_PROMPT` and `_FINAL_SYSTEM_PROMPT` context |
| `tests/unit/test_classification_agent.py` | Modify | Add mocked test for description question and save |
| `tests/unit/test_configuration_agent.py` | Modify | Add mocked test verifying description appears in agent system prompt |

### Out of scope

- Changes to Tasks 10–12 agent prompts (they will inherit the description via the shared context loader)
- UI changes beyond saving/loading the description field
- Validation of the description content (free text, no constraints)
- Status updates to CLAUDE.md or tasks.json (separate closure subtask if needed)
- Architecture doc updates to `configuracion.md` or `clasificacion.md`

---

## Key design decisions

**Where to ask the question**
In the Clasificación section, as part of the normal conversation flow after the agent
diagnoses the standardization level. The description question must happen *before* the
operator clicks Confirm — it is a conversational turn, not a post-confirm step. The agent
asks it once `standardization_level` is non-None in `_data_store`.

**Where to store it**
On the existing restaurant entity in DataLake (same entity saved by bienvenida.py).
Add a `description` field to the restaurant dict. No schema migration needed for
JsonStorage; SqliteStorage may need a column addition (see Risk #3).

**How to thread it downstream**
`_load_configuration_context` in `configuracion.py` is the single point that loads session
context for all configuration agents. Adding `restaurant_description` there means every
agent that receives this context dict gets it automatically — including future agents in
Tasks 10–12 if they use the same loader pattern.

**What the description looks like in prompts**
A single line in the operator context block:
```
Descripción del restaurante: Taquería de barrio, servicio en mostrador, ~30 cubiertos,
enfocada en tacos y quesadillas para el almuerzo y comida.
```

---

## Codebase state (verified 2026-03-19)

### ClassificationAgent (`core/agents/classification_agent.py`)
- `_data_store` currently holds only `standardization_level`.
- `_SYSTEM_PROMPT` ends with the JSON format section (`reply` + `standardization_level`).
- `_ClassificationResponse` Pydantic model has fields: `reply: str`, `standardization_level: int | None`.
- `_process_response` stores `standardization_level` when non-None.
- **No `restaurant_confirmed` field exists.** The agent does not know when the operator
  confirms — it only knows when it has diagnosed a level. The description question must
  be triggered by the agent itself after diagnosing the level, not by a confirm signal.

### clasificacion.py (`gradio_app/sections/clasificacion.py`)
- `_make_confirm_fn` saves only `classification` entity (line 70):
  `data_lake.save_entity("classification", entity_id, {"standardization_level": level})`
- It does **not** save or update the `restaurant` entity — that is saved by bienvenida.py.
- To save the description, `confirm_fn` must: (1) read `description` from agent `_data_store`,
  (2) load the existing restaurant entity, (3) add `description` to it, (4) re-save it.
- `_load_classification_context` (line 22) loads the restaurant entity to get `restaurant_name`
  and `restaurant_type` — this is where the description could also be loaded for display.

### _load_configuration_context (`gradio_app/sections/configuracion.py`, line 117–146)
- Returns dict with: `restaurant_type_id`, `restaurant_type`, `restaurant_name`,
  `standardization_level`.
- Loads `restaurant` entity (line 125) and `classification` entity (line 135).
- Adding `restaurant_description` requires reading `restaurant_data.get("description", "")`.

### ConfigurationAgent (`core/agents/configuration_agent.py`)
- `_generate_prompt` (line 194–243) builds `context_parts` list with operator context.
- `context.get("restaurant_description", "")` would be a one-line addition.

### ConsistencyCheckAgent (`core/agents/consistency_check_agent.py`)
- `_generate_prompt` (line 187–210) builds JSON user messages for both modes.
- Adding `restaurant_description` to the JSON dict alongside `restaurant_type` in both
  per-step and final calls.
- The system prompts (`_PER_STEP_SYSTEM_PROMPT`, `_FINAL_SYSTEM_PROMPT`) mention
  `restaurant_type` in their input field descriptions — need to add `restaurant_description`.

### SQLite schema (`core/storage/schema.py`)
- `restaurant` table (line 24–30): columns are `id`, `name`, `address`,
  `restaurant_type_id`, `notes`. No `description` column.
- **Resolved (17.1):** SqliteStorage uses **typed columns** for `restaurant` (silently
  drops unknown keys) but a **JSON blob** for `classification` (preserves any keys).
  Decision: store `restaurant_description` in the classification entity alongside
  `standardization_level`. See `.taskmaster/docs/task-17/17.1/plan.md` for full analysis.

---

## Implementation steps

### Step 1 — Verify restaurant entity storage path

Read `bienvenida.py` to confirm how the restaurant entity is saved (typed columns vs JSON
blob). This determines whether `schema.py` needs an `ALTER TABLE` for a `description` column.

### Step 2 — Update ClassificationAgent

**File:** `core/agents/classification_agent.py`

1. Add `description: str | None = None` to `_ClassificationResponse`.
2. Add a section to `_SYSTEM_PROMPT` after the level diagnosis rules:
   ```
   ## Descripción del restaurante

   Una vez que hayas diagnosticado el nivel de estandarización (standardization_level no es null),
   pregunta al operador: "¿Podrías describir tu restaurante en una frase? Por ejemplo: tipo de
   cocina, estilo de servicio, tamaño, zona." Guarda la respuesta en el campo "description".

   Si el operador no quiere responder o dice que no sabe, acepta y deja description en null.
   No insistas.
   ```
3. Update the JSON format section to include `"description"`.
4. In `_process_response`, store `description` when non-None:
   ```python
   description = data.get("description")
   if description is not None:
       self.store("restaurant_description", description)
   ```
5. Add `restaurant_description` to `OUTPUT_SCHEMA`.

### Step 3 — Update clasificacion.py confirm flow

**File:** `gradio_app/sections/clasificacion.py`

Save `restaurant_description` in the **classification** entity alongside
`standardization_level` (decided in 17.1 — classification uses JSON blob, no schema
changes needed).

1. In `_make_confirm_fn`, load the agent state to retrieve `restaurant_description`
   from `_data_store`.
2. Include it in the classification entity dict:
   ```python
   data_lake.save_entity("classification", entity_id, {
       "standardization_level": level,
       "restaurant_description": description,
   })
   ```

### Step 4 — Update _load_configuration_context

**File:** `gradio_app/sections/configuracion.py`

Add to the returned dict (from classification entity, per 17.1 decision):
```python
"restaurant_description": classification_data.get("restaurant_description", "")
```

### Step 5 — Update ConfigurationAgent prompt

**File:** `core/agents/configuration_agent.py`

In `_generate_prompt`, after the existing context parts:
```python
restaurant_description = context.get("restaurant_description", "")
if restaurant_description:
    context_parts.append(f"Descripción del restaurante: {restaurant_description}")
```

### Step 6 — Update ConsistencyCheckAgent prompts

**File:** `core/agents/consistency_check_agent.py`

1. In `_generate_prompt`, add `"restaurant_description"` to both JSON dicts:
   - Per-step: `"restaurant_description": input_data.get("restaurant_description", "")`
   - Final: same pattern.
2. Update `_PER_STEP_SYSTEM_PROMPT` input field description to mention `restaurant_description`.
3. Update `_FINAL_SYSTEM_PROMPT` input field description to mention `restaurant_description`.
4. Add a line to both prompts' criteria: "Use the restaurant description to evaluate semantic
   relevance more precisely."

### Step 7 — Update configuracion.py caller sites

**File:** `gradio_app/sections/configuracion.py`

The context dict from `_load_configuration_context` is already passed to both agents.
Verify that the ConsistencyCheckAgent call sites (lines 321–336, 482–494) also pass
`restaurant_description` in `input_data`. Currently they pass `restaurant_type` from ctx —
need to also pass `restaurant_description`.

### Step 8 — Update tests

**File:** `tests/unit/test_classification_agent.py`
- Add mocked test: after agent returns `standardization_level`, next turn asks for description.
  Verify `restaurant_description` stored in `_data_store`.

**File:** `tests/unit/test_configuration_agent.py`
- Add mocked test: pass `restaurant_description` in context, verify it appears in the
  generated system prompt string.

### Step 9 — End-to-end verification

Manual test:
1. Run Clasificación section, complete diagnosis.
2. Verify agent asks for description.
3. Provide description, click Confirm.
4. Open Configuración section, chat with agent.
5. Verify description appears in agent behavior (restaurant-specific suggestions).
6. Click Confirm on a step, verify ConsistencyCheckAgent uses description.

---

## Test coverage

### Mocked tests

| Test | File | Validates |
|------|------|-----------|
| Description question after level diagnosed | `test_classification_agent.py` | Agent asks for description when `standardization_level` is set, stores `restaurant_description` in `_data_store` |
| Description in configuration prompt | `test_configuration_agent.py` | `restaurant_description` from context appears in generated system prompt |

### Live tests

The plan does not include live tests. Given that the ClassificationAgent flow changes
(new conversational turn), a live test verifying the description question would be
valuable. Consider adding one guarded by `ANTHROPIC_API_KEY`, following the existing
live test pattern in `test_configuration_agent.py`.

---

## Risks and open questions

### Risk 1 — Restaurant entity save path (RESOLVED in 17.1)

**Decision:** Store `restaurant_description` in the **classification** entity alongside
`standardization_level`. The restaurant entity uses typed SQLite columns (would require
schema migration); the classification entity uses a JSON blob (zero changes needed).
See `.taskmaster/docs/task-17/17.1/plan.md` for full analysis.

### Risk 2 — Agent conversation flow

The ClassificationAgent has no `restaurant_confirmed` field. The description question must
be triggered by the agent itself after it diagnoses a level (when `standardization_level`
is non-None). The agent needs prompt instructions to ask the question once and not repeat
it. The `_data_store` draft injection already exists — adding `restaurant_description` to
the draft block will signal to the agent that the question was already asked/answered.

### Risk 3 — SQLite schema (RESOLVED in 17.1)

No schema changes needed. The classification entity uses a generic JSON `data` column,
so adding `restaurant_description` to the dict is transparent to the storage layer.

### Risk 4 — Missing plan completeness items

- **Re-exports:** No new classes — not needed.
- **Status updates:** Not mentioned. Should mark Task 17 done in tasks.json and update
  CLAUDE.md upon completion.
- **Architecture docs:** `clasificacion.md` and `configuracion.md` may need minor updates
  to reflect the new `restaurant_description` field in context.

---

## Deliverable checklist

### `core/agents/classification_agent.py`
- [ ] `_ClassificationResponse` includes `description` field
- [ ] `_SYSTEM_PROMPT` includes description question instructions
- [ ] `_process_response` stores `restaurant_description` in `_data_store`
- [ ] `OUTPUT_SCHEMA` includes `restaurant_description`

### `gradio_app/sections/clasificacion.py`
- [ ] `confirm_fn` saves description to DataLake (classification or restaurant entity)
- [ ] Agent state loaded to retrieve description before save

### `gradio_app/sections/configuracion.py`
- [ ] `_load_configuration_context` returns `restaurant_description`
- [ ] ConsistencyCheckAgent call sites pass `restaurant_description` in `input_data`

### `core/agents/configuration_agent.py`
- [ ] `_generate_prompt` includes `restaurant_description` in context block

### `core/agents/consistency_check_agent.py`
- [ ] `_PER_STEP_SYSTEM_PROMPT` mentions `restaurant_description` in input fields
- [ ] `_FINAL_SYSTEM_PROMPT` mentions `restaurant_description` in input fields
- [ ] `_generate_prompt` passes `restaurant_description` in both JSON dicts

### Tests
- [ ] Mocked test: classification agent description question + store
- [ ] Mocked test: configuration agent prompt includes description
- [ ] End-to-end manual verification: Clasificación → Configuración → ConsistencyCheck

---

## Context captured during planning (2026-03-19)

This task was identified during Task 9 implementation while refining the ConfigurationAgent
and ConsistencyCheckAgent. The consistency check was improved to flag semantic mismatches
(e.g. "azucar" as a recipe category), but the check is still generic because it only knows
the restaurant type label. A richer description would make the semantic checks
restaurant-specific and dramatically improve the quality of agent suggestions in all
downstream sections.

The decision to add this before Task 10 (not after the full pipeline) was deliberate:
retrofitting a new context field across 3+ already-built tasks is harder and riskier than
building it in now when Tasks 10–12 haven't started yet.
