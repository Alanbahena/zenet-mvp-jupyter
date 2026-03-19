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

- Task 9 done ✓ (ConfigurationAgent, ConsistencyCheckAgent, configuracion.py all built)
- Task 8 done ✓ (ClassificationAgent and clasificacion.py built)

---

## Scope

### What changes

| File | Action | Summary |
|------|--------|---------|
| `core/agents/classification_agent.py` | Modify | Add follow-up question after restaurant type is confirmed — ask for a short free-text description of the restaurant |
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

---

## Key design decisions

**Where to ask the question**
In the Clasificación section, after the operator confirms restaurant type and standardization
level. The ClassificationAgent already ends with a confirmation — the description question
is a natural follow-up before the section closes.

**Where to store it**
On the existing restaurant entity in DataLake (same entity saved by clasificacion.py).
Add a `description` field to the restaurant dict. No schema migration needed for JsonStorage;
SqliteStorage may need a column addition.

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

## Context captured during planning (2026-03-19)

This task was identified during Task 9 implementation while refining the ConfigurationAgent
and ConsistencyCheckAgent. The consistency check was improved to flag semantic mismatches
(e.g. "azúcar" as a recipe category), but the check is still generic because it only knows
the restaurant type label. A richer description would make the semantic checks
restaurant-specific and dramatically improve the quality of agent suggestions in all
downstream sections.

The decision to add this before Task 10 (not after the full pipeline) was deliberate:
retrofitting a new context field across 3+ already-built tasks is harder and riskier than
building it in now when Tasks 10–12 haven't started yet.

---

## Implementation steps (high level)

1. Read `clasificacion.py` and `classification_agent.py` to understand the current
   confirmation flow and where the restaurant entity is saved.
2. Add a description question to `ClassificationAgent` — triggered after `restaurant_confirmed`
   is set, as a new conversational turn.
3. Save `description` to the restaurant entity dict in `clasificacion.py`.
4. Update `_load_configuration_context` in `configuracion.py` to load and expose
   `restaurant_description`.
5. Inject into `ConfigurationAgent._generate_prompt` context block.
6. Inject into both `ConsistencyCheckAgent` system prompts.
7. Update tests.
8. Verify end-to-end: description captured in Clasificación → visible in ConfigurationAgent
   system prompt → ConsistencyCheckAgent uses it for per-step checks.
