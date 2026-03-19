# Subtask 9.6 — Documentation and Task Closure

## Context

Final subtask of Task 9. Creates the Configuración section architecture doc, updates two
existing architecture docs, updates CLAUDE.md with current project state, and marks all
Task 9 entries done in `tasks.json`.

**Prior (9.5):** Full test suite green — 16 mocked + 3 live tests.

**Next (Task 17):** Restaurant profile enrichment — reads Task 9 status as `done` and
the `configuracion.md` architecture doc as reference.

---

## Files to Create / Modify

| File | Action | Summary |
|------|--------|---------|
| `docs/Architecture/sections/configuracion.md` | Create | Full section architecture doc |
| `docs/Architecture/architecture-agent-framework.md` | Modify | Add ConfigurationAgent + ConsistencyCheckAgent to diagram and table |
| `docs/Architecture/architecture-gradio-and-langgraph.md` | Modify | Update 3 stale spots (section table, overview text, implementation files) |
| `CLAUDE.md` | Modify | Task table, project structure, sections comment, architecture table |
| `.taskmaster/tasks/tasks.json` | Modify | Mark all Task 9 subtasks + parent done |

---

## Dependencies

- 9.1–9.5 done
- `docs/Architecture/sections/clasificacion.md` exists as structural reference
- No packages, no env vars, no code changes

---

## Implementation Steps

### Step 1 — Create `docs/Architecture/sections/configuracion.md`

Mirror the structure of `sections/clasificacion.md`. Document the actual implementation
(not the original plan — the implementation evolved significantly). Must include:

**Section 1 — Overview**
- Two-column layout: chat left, sequential step UI right
- Entities produced: `category_recipe`, `family_inventory`, `recipe_unit`, `inventory_unit`
- Implementation files table: `configuracion.py`, `configuration_agent.py`, `consistency_check_agent.py`

**Section 2 — Sequential Step Pattern**
- Four steps in fixed order: categories → families → recipe_units → inventory_units
- One step visible at a time, progress indicator at top
- `gr.Dataframe(wrap=True, interactive=False)` with per-step column widths
- `_STEP_KEYS`, `_STEP_TITLES`, `_STEP_COLUMNS`, `_STEP_COLUMN_LABELS`, `_STEP_COLUMN_WIDTHS`
- Resume on load via `_init_section()` → `data_lake.list_entity_ids()` per entity type

**Section 3 — ConfigurationAgent**
- Single agent across all 4 steps, continuous conversation
- `_data_store` schema: `current_step`, `categories`, `families`, `recipe_units`, `inventory_units`
- Level-based tone: Level 1 (build from scratch) vs Level 2/3 (confirm/adjust)
- `__confirmed__` trigger: agent introduces the next step after confirm
- `__issues__` trigger: agent proposes corrected entities after consistency check warnings
- Memory injection: `agent.memory.add_assistant(initial_greeting_text)` on first turn
- Description field rules: short, operator-facing, no Zenet internals, no costs
- Symbol field rules: always required for units, standard kitchen abbreviations

**Section 4 — ConsistencyCheckAgent**
- Two modes: per-step check (single list) and final cross-entity check (all four lists)
- Structural gap checks per step type
- Semantic relevance checks (entity name must match entity type)
- `_ConsistencyCheckResponse`: `issues`, `suggestions`, `looks_good`

**Section 5 — Consistency Check + Agent Correction Flow**
- First click: "Verificando consistencia..." → ConsistencyCheckAgent runs
- Issues found: warning in `status_md` + agent fires with `__issues__:` trigger
- Agent proposes corrected entities → table updates → `issues_ack` resets to `False`
- No issues: save immediately, agent fires with `__confirmed__:` trigger for next step
- Second click (override): saves regardless, no re-check
- `show_progress="hidden"` on confirm button to suppress orange outlines
- Generator pattern: intermediate `yield` for loading states

**Section 6 — Persistence**
- `_save_step()`: assigns sequential IDs from 1, calls `data_lake.save_entity_obj()`
- `_ENTITY_BUILDERS`: lambda dict mapping step key to entity constructor
- `_load_configuration_context()`: loads restaurant type, name, standardization level
- Classification fallback to Level 1 when entity missing

**Section 7 — Status Messages**
- Per-step status: "**{saved step}** guardadas. Siguiente: **{next step}** — {description}."
- Final status: "**{last step}** guardadas. Configuración completa — ya puedes continuar con Alineamiento."
- `_STEP_DESCRIPTIONS` dict with one-line Spanish descriptions per step

---

### Step 2 — Update `docs/Architecture/architecture-agent-framework.md`

Two changes:

1. **Mermaid diagram** (line 15): Change
   ```
   T712["Tasks 7–12<br/>Notebook Agents<br/>WelcomeAgent ✓<br/>ClassificationAgent ✓<br/>..."]
   ```
   to:
   ```
   T712["Tasks 7–12<br/>Notebook Agents<br/>WelcomeAgent ✓<br/>ClassificationAgent ✓<br/>ConfigurationAgent ✓<br/>ConsistencyCheckAgent ✓<br/>..."]
   ```

2. **Layer table** (line 27): Change
   ```
   Concrete agents extending `BaseAgent` (`WelcomeAgent` done, `ClassificationAgent` done; 9–12 pending)
   ```
   to:
   ```
   Concrete agents extending `BaseAgent` (`WelcomeAgent` done, `ClassificationAgent` done, `ConfigurationAgent` done, `ConsistencyCheckAgent` done; 10–12 pending)
   ```

---

### Step 3 — Update `docs/Architecture/architecture-gradio-and-langgraph.md`

Three changes:

1. **Overview text** (line 26): Change
   ```
   Task 7 (Bienvenida) is complete.
   ```
   to:
   ```
   Tasks 7 (Bienvenida), 8 (Clasificación), and 9 (Configuración) are complete.
   ```

2. **Section-to-task table** (line 107): Change
   ```
   | Configuración | `sections/configuracion.py` | stub (Task 9) |
   ```
   to:
   ```
   | Configuración | `sections/configuracion.py` | **done** (Task 9) |
   ```

3. **Implementation Files — sections row** (line 401): Change
   ```
   Section implementations: Bienvenida done (Task 7); five stubs remaining (Tasks 8–12)
   ```
   to:
   ```
   Section implementations: Bienvenida (Task 7), Clasificación (Task 8), Configuración (Task 9) done; three stubs remaining (Tasks 10–12)
   ```

---

### Step 4 — Update `CLAUDE.md`

Four changes:

1. **Task status table** (lines 157–169): Replace the collapsed `9–16` row with individual
   rows reflecting current state:
   ```
   | 9  | Configuración section agent           | **done** |
   | 10 | Alineamiento section                   | pending  |
   | 11 | Estructura section                     | pending  |
   | 12 | Manual operativo section               | pending  |
   | 13 | Gradio UI entry point (cancelled)      | cancelled |
   | 14 | Notebook pipeline orchestration (cancelled) | cancelled |
   | 15 | Unit and integration tests             | pending  |
   | 16 | Documentation and user guide           | pending  |
   | 17 | Restaurant profile enrichment          | pending  |
   ```
   Change "Task 9 is the next task" to "Task 17 (Restaurant profile enrichment) is next,
   prerequisite for Task 10."

2. **Project structure — `core/agents/`** (lines 74–78): Add missing agent files:
   ```
   agents/                # Agent framework
     base_agent.py        # BaseAgent abstract class
     simple_agent.py      # RestaurantInfoAgent
     welcome_agent.py     # WelcomeAgent (Task 7)
     classification_agent.py  # ClassificationAgent (Task 8)
     configuration_agent.py   # ConfigurationAgent (Task 9)
     consistency_check_agent.py # ConsistencyCheckAgent (Task 9)
     utils.py             # create_agent() factory, AgentRegistry
     graph_utils.py       # BaseGraphState, make_agent_node(), build_sequential_graph()
   ```

3. **`sections/` comment** (lines 85–87): Change
   ```
   sections/              # One file per pipeline section (stubs — replaced by Tasks 7–12)
   ```
   to:
   ```
   sections/              # One file per pipeline section (Tasks 7–9 done; 10–12 stubs)
   ```

4. **Architecture Documentation table** (lines 209–221): Add missing entries:
   ```
   | Agent framework                        | `architecture-agent-framework.md`            |
   | Bienvenida section                     | `sections/bienvenida.md`                     |
   | Clasificación section                  | `sections/clasificacion.md`                  |
   | Configuración section                  | `sections/configuracion.md`                  |
   ```

---

### Step 5 — Update `.taskmaster/tasks/tasks.json`

Mark the following as `done`:
- Subtasks 9.1, 9.2, 9.3, 9.4 (old design entries — currently `in-progress`)
- Subtask 9.10 (this subtask — currently `pending`)
- Parent Task 9 (currently `in-progress`)

Subtasks 9.5–9.9 are already `done`.

---

## Out of Scope

- Any code changes to agents, UI, or tests
- Changes to `schema.py`, `persistence.py`, or `data_model.py`
- Tests for `_load_configuration_context` or `_init_section`
- Task 17 execution (already has its own plan)
- Changes to `sections/bienvenida.md` or `sections/clasificacion.md` (no stale references)

---

## Deliverable Checklist

### `docs/Architecture/sections/configuracion.md`
- [ ] Sequential step pattern documented
- [ ] Consistency check pattern (per-step + cross-entity) documented
- [ ] Agent correction flow (`__issues__` + `__confirmed__` triggers) documented
- [ ] Resume behavior documented
- [ ] `_data_store` schema documented
- [ ] Status message format documented

### `docs/Architecture/architecture-agent-framework.md`
- [ ] Mermaid diagram includes `ConfigurationAgent ✓` and `ConsistencyCheckAgent ✓`
- [ ] Layer table includes both agents as done

### `docs/Architecture/architecture-gradio-and-langgraph.md`
- [ ] Overview text reflects Tasks 7, 8, 9 complete
- [ ] Section-to-task table: Configuración row → `**done** (Task 9)`
- [ ] Implementation Files table: 3 done, 3 stubs remaining

### `CLAUDE.md`
- [ ] Task status table expanded with individual rows, Task 9 → done, Task 17 added
- [ ] "Next task" line updated to Task 17
- [ ] Project structure lists all 6 agent files
- [ ] `sections/` comment reflects Tasks 7–9 done
- [ ] Architecture Documentation table includes 4 new entries

### `.taskmaster/tasks/tasks.json`
- [ ] Subtasks 9.1–9.4 (old) → `done`
- [ ] Subtask 9.10 → `done`
- [ ] Parent Task 9 → `done`
