# Subtask 9.3 — Configuración Section UI (`gradio_app/sections/configuracion.py`)

## Context

Replaces the 7-line stub in `gradio_app/sections/configuracion.py` with a full `render()`
that wires `ConfigurationAgent` and `ConsistencyCheckAgent` into a sequential 4-step UI.

**Prior (9.1 + 9.2):** `ConfigurationAgent` and `ConsistencyCheckAgent` are implemented.
`save_state`/`load_state` work. Both agents accept the input shapes this UI will pass.

**Next (9.4):** Exports both agents from `core/agents/__init__.py` and `core/__init__.py`.
9.3 imports agents directly from their modules — 9.4 handles re-exports.

---

## File to Modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/configuracion.py` | Modify | Replace stub with full `render()` |

---

## Dependencies

- 9.1 done — `core/agents/configuration_agent.py` with `ConfigurationAgent`
- 9.2 done — `core/agents/consistency_check_agent.py` with `ConsistencyCheckAgent`
- `data_lake.list_ids(entity_type) -> list[str]` — exists in `DataLake`
- `data_lake.save_entity_obj(entity)` — exists in `DataLake`
- `data_lake.load_entity("restaurant", entity_id)` and `load_entity("classification", entity_id)`
- `data_lake.load_entity("agent_state", session_id)` / `save_entity(...)` — used by `load_state`/`save_state`
- `DEFAULT_RESTAURANT_TYPES` in `core.domain.data_model`
- `CategoryRecipe`, `FamilyInventory`, `RecipeUnit`, `InventoryUnit` dataclasses from `core.domain.data_model`
- `ClaudeProvider` in `core.ai.providers`
- `create_agent` in `core.agents.utils`
- `ANTHROPIC_API_KEY` in `.env` (live tests only — 9.5)

---

## Key Design Decisions

### D1 — Sequential step UI
One entity type visible at a time. Progress indicator at top, single `gr.Dataframe` below,
confirm button at bottom. Keeps agent conversation and UI in sync.

### D2 — `gr.Dataframe(interactive=False)`
Read-only display for MVP. All entity edits go through chat. Avoids state sync complexity
between the Dataframe and the draft `gr.State`.

### D3 — Two-click confirm for consistency issues
`issues_acknowledged = gr.State(False)`.
- First click: run `ConsistencyCheckAgent`, if issues found → show in status markdown,
  set `issues_acknowledged=True`. Do NOT save.
- Second click: save regardless — operator has acknowledged the issues.
- If no issues: save on first click (no second click needed).

### D4 — Dynamic initial greeting
`_initial_greeting(restaurant_type, template_preview)` is a function, not a constant.
Called inside `render()` after `_load_configuration_context()` so it can reference the
operator's actual restaurant type and template.

### D5 — Classification fallback to Level 1
If no `classification` entity exists in DataLake, `standardization_level` defaults to `1`.
Never blocks section from rendering.

### D6 — Resume on load
`_init_section()` calls `list_ids()` for all four entity types and returns the index of
the first step with no saved entities. Section opens at that step. Steps with existing
entities are shown as complete in the progress indicator.

### D7 — Save via confirm button only
No agent-triggered save. Consistent with Tasks 7 and 8.

### D8 — Non-standard inventory units
Saved with `factor_to_base=1.0` as a placeholder. Equivalences are handled in Task 10.

---

## Implementation Steps

### 1. Imports

```python
import gradio as gr

from core.agents.configuration_agent import ConfigurationAgent
from core.agents.consistency_check_agent import ConsistencyCheckAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import (
    DEFAULT_RESTAURANT_TYPES,
    CategoryRecipe,
    FamilyInventory,
    RecipeUnit,
    InventoryUnit,
)
```

### 2. Module-level constants

```python
_STEP_KEYS = ["categories", "families", "recipe_units", "inventory_units"]

_STEP_TITLES = {
    "categories":      "Categorías de recetas",
    "families":        "Familias de inventario",
    "recipe_units":    "Unidades de receta",
    "inventory_units": "Unidades de inventario",
}

# Column headers for gr.Dataframe per step
_STEP_COLUMNS = {
    "categories":      ["name", "description"],
    "families":        ["name", "description"],
    "recipe_units":    ["name", "symbol", "description"],
    "inventory_units": ["name", "symbol", "is_standard", "description"],
}
```

### 3. `_load_configuration_context(data_lake, session_id) -> dict`

- `entity_id = abs(hash(session_id)) % (2**31 - 1)` — same derivation as `clasificacion.py:23`
- Load `restaurant` entity → extract `restaurant_type_id`, look up name via `DEFAULT_RESTAURANT_TYPES`
- Load `classification` entity → extract `standardization_level`, default to `1` if absent
- Return:
  ```python
  {
      "restaurant_type_id":    int,
      "restaurant_type":       str,
      "restaurant_name":       str,
      "standardization_level": int,
  }
  ```

### 4. `_init_section(data_lake, session_id) -> int`

- Call `data_lake.list_ids("category_recipe")`, `"family_inventory"`, `"recipe_unit"`, `"inventory_unit"`
- Map: step index 0 → `"category_recipe"`, 1 → `"family_inventory"`, 2 → `"recipe_unit"`, 3 → `"inventory_unit"`
- Return first index where `list_ids()` is empty; return `4` if all four have entries

### 5. `_initial_greeting(restaurant_type, template_preview, standardization_level) -> list[dict]`

Branches on `standardization_level`. Level 1 presents the template preview inline and
invites the operator to adjust. Level 2/3 acknowledges their experience and frames the
template as a reference — the template preview is NOT shown in the greeting; the agent
surfaces it naturally in the first conversational turn.

Avoid "I see you already have something" literally — the level signals likely structure,
not that any data has been uploaded yet. Prefer "ya tienes experiencia documentando tu
operación."

```python
def _initial_greeting(
    restaurant_type: str,
    template_preview: str,
    standardization_level: int,
) -> list[dict]:
    if standardization_level == 1:
        content = (
            "Perfecto. Ahora vamos a configurar la estructura base de tu restaurante — "
            "las categorías de recetas, familias de inventario, y unidades de medida. "
            "Vamos a construirlo juntos desde cero. "
            f"Para un restaurante {restaurant_type}, Zenet sugiere empezar con estas "
            f"categorías de recetas: {template_preview}. "
            "¿Te parece bien o quieres ajustar algo?"
        )
    else:
        content = (
            "Perfecto. Ahora vamos a configurar la estructura base de tu restaurante — "
            "las categorías de recetas, familias de inventario, y unidades de medida. "
            "Ya tienes experiencia documentando tu operación, así que esto debería ir rápido. "
            "Te voy a compartir lo que Zenet sugiere para tu tipo de restaurante como punto "
            "de referencia — ajusta lo que no cuadre con lo que ya manejas. "
            "Empecemos con las categorías de recetas. ¿Listo?"
        )
    return [{"role": "assistant", "content": content}]
```

Called inside `render()` after `_load_configuration_context()`. Receives
`standardization_level` from the context dict.

### 6. `_make_progress_md(current_step: int) -> str`

Returns a markdown string showing step completion status:
`[Categorías ✓] → [Familias →] → [Unidades R] → [Unidades I]`

Completed steps (index < current_step) show ✓. Active step shows →. Future steps show plain name.

### 7. `_draft_to_rows(draft: list[dict], step_key: str) -> list[list]`

Converts a list of entity dicts to rows for `gr.Dataframe` using `_STEP_COLUMNS[step_key]`
as the column order. Returns `[]` if draft is empty.

### 8. `_make_chat_fn(provider, data_lake)`

Pattern: identical to `clasificacion.py:35–58`.

```python
def _make_chat_fn(provider, data_lake):
    def chat_fn(message, history, session_id, current_step,
                draft_cats, draft_fams, draft_ru, draft_iu):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, "", draft_cats, draft_fams, draft_ru, draft_iu, False
        if not (message or "").strip():
            return history, "", draft_cats, draft_fams, draft_ru, draft_iu, False

        agent = create_agent(ConfigurationAgent, provider=provider, name="configuration_agent")
        agent.load_state(data_lake, session_id=f"configuration_agent_{session_id}")
        ctx = _load_configuration_context(data_lake, session_id)
        ctx["current_step"] = _STEP_KEYS[current_step]

        try:
            result = agent.run(input_data={"user_message": message}, context=ctx)
            reply = result["reply"]
            entities = result["entities"]
            step_complete = bool(result.get("step_complete"))
        except Exception:
            reply = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
            entities = None
            step_complete = False

        agent.save_state(data_lake, session_id=f"configuration_agent_{session_id}")

        history = list(history)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})

        # Update only the current step's draft
        drafts = [draft_cats, draft_fams, draft_ru, draft_iu]
        if entities is not None:
            drafts[current_step] = entities

        return history, "", drafts[0], drafts[1], drafts[2], drafts[3], step_complete
    return chat_fn
```

### 9. `_make_confirm_fn(data_lake)`

```python
def _make_confirm_fn(data_lake):
    def confirm_fn(current_step, draft_cats, draft_fams, draft_ru, draft_iu,
                   issues_ack, session_id):
        if not session_id:
            return "Sesión no iniciada. Recarga la página.", False, current_step, False

        ctx = _load_configuration_context(data_lake, session_id)
        restaurant_type = ctx.get("restaurant_type", "")
        drafts = [draft_cats, draft_fams, draft_ru, draft_iu]
        step_key = _STEP_KEYS[current_step]
        current_draft = drafts[current_step]

        # --- Run consistency check ---
        check_agent = create_agent(ConsistencyCheckAgent, provider=ClaudeProvider(), name="consistency_check")

        if current_step == 3 and not issues_ack:
            # Final step: run cross-entity check
            try:
                check_result = check_agent.run(input_data={
                    "categories":      draft_cats,
                    "families":        draft_fams,
                    "recipe_units":    draft_ru,
                    "inventory_units": draft_iu,
                    "restaurant_type": restaurant_type,
                })
            except Exception:
                check_result = {"looks_good": True, "issues": [], "suggestions": []}
        else:
            # Per-step check
            try:
                check_result = check_agent.run(input_data={
                    "step":            step_key,
                    "entities":        current_draft,
                    "restaurant_type": restaurant_type,
                })
            except Exception:
                check_result = {"looks_good": True, "issues": [], "suggestions": []}

        looks_good = check_result.get("looks_good", True)
        issues = check_result.get("issues", [])

        # --- Two-click confirm ---
        if not looks_good and not issues_ack:
            issues_md = "**Advertencias antes de confirmar:**\n" + "\n".join(f"- {i}" for i in issues)
            issues_md += "\n\nHaz clic en **Confirmar** de nuevo para guardar de todas formas."
            return issues_md, True, current_step, False  # issues_acknowledged = True

        # --- Save ---
        _save_step(data_lake, step_key, current_draft)

        new_step = current_step + 1
        if new_step > 3:
            status = "Configuración completada. Ya puedes continuar con Alineamiento."
        else:
            status = f"Paso guardado. Ahora: **{_STEP_TITLES[_STEP_KEYS[new_step]]}**"

        return status, False, new_step, False  # reset issues_acknowledged and step_complete
    return confirm_fn
```

### 10. `_save_step(data_lake, step_key, draft)`

Assigns sequential IDs and calls `data_lake.save_entity_obj()` for each entity.

```python
_ENTITY_BUILDERS = {
    "categories":      lambda i, e: CategoryRecipe(id=i, name=e["name"], description=e.get("description")),
    "families":        lambda i, e: FamilyInventory(id=i, name=e["name"], description=e.get("description")),
    "recipe_units":    lambda i, e: RecipeUnit(id=i, name=e["name"], symbol=e["symbol"], description=e.get("description")),
    "inventory_units": lambda i, e: InventoryUnit(
        id=i, name=e["name"], symbol=e["symbol"],
        is_standard=e.get("is_standard", False),
        factor_to_base=e.get("factor_to_base", 1.0),
        description=e.get("description"),
    ),
}

def _save_step(data_lake, step_key: str, draft: list[dict]) -> None:
    builder = _ENTITY_BUILDERS[step_key]
    for idx, entity_dict in enumerate(draft, start=1):
        entity = builder(idx, entity_dict)
        data_lake.save_entity_obj(entity)
```

### 11. `render(session_id, data_lake)`

```python
def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()
    ctx = _load_configuration_context(data_lake, None)  # static preview only
    # ... build initial greeting dynamically after session is known via on-load event
    # Use gr.on(triggers=[...]) or init from a gr.State default factory if needed

    # --- State ---
    current_step_state  = gr.State(_init_section(data_lake, ""))  # refined on real session load
    draft_categories    = gr.State([])
    draft_families      = gr.State([])
    draft_recipe_units  = gr.State([])
    draft_inv_units     = gr.State([])
    step_complete_state = gr.State(False)
    issues_acknowledged = gr.State(False)

    # --- Layout ---
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de configuración")
            chatbot    = gr.Chatbot(label="Asistente Zenet", height="60vh",
                                    value=_initial_greeting("tu tipo de restaurante", "", 1))
            textbox    = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
            send_btn   = gr.Button("Enviar")

        with gr.Column(scale=1):
            progress_md    = gr.Markdown(_make_progress_md(0))
            step_title_md  = gr.Markdown(f"### {_STEP_TITLES['categories']}")
            entity_table   = gr.Dataframe(
                headers=_STEP_COLUMNS["categories"],
                interactive=False,
                label="Entidades propuestas",
            )
            confirm_btn    = gr.Button("Confirmar y continuar", interactive=False)
            status_md      = gr.Markdown("")

    # --- Handlers ---
    chat_fn = _make_chat_fn(provider, data_lake)
    confirm_fn = _make_confirm_fn(data_lake)

    def _chat_and_format(message, history, session_id,
                         current_step, draft_cats, draft_fams, draft_ru, draft_iu):
        history, text, d_cats, d_fams, d_ru, d_iu, s_complete = chat_fn(
            message, history, session_id, current_step,
            draft_cats, draft_fams, draft_ru, draft_iu,
        )
        step_key = _STEP_KEYS[min(current_step, 3)]
        drafts = [d_cats, d_fams, d_ru, d_iu]
        rows = _draft_to_rows(drafts[current_step], step_key)
        progress = _make_progress_md(current_step)
        title = f"### {_STEP_TITLES[step_key]}"
        btn = gr.Button(interactive=s_complete)
        return history, text, d_cats, d_fams, d_ru, d_iu, s_complete, btn, rows, progress, title

    def _confirm_and_advance(current_step, draft_cats, draft_fams, draft_ru, draft_iu,
                              issues_ack, session_id):
        status, new_issues_ack, new_step, step_complete_reset = confirm_fn(
            current_step, draft_cats, draft_fams, draft_ru, draft_iu, issues_ack, session_id,
        )
        new_step_clamped = min(new_step, 3)
        step_key = _STEP_KEYS[new_step_clamped]
        progress = _make_progress_md(new_step)
        title = f"### {_STEP_TITLES[step_key]}"
        drafts = [draft_cats, draft_fams, draft_ru, draft_iu]
        rows = _draft_to_rows(drafts[new_step_clamped], step_key)
        btn = gr.Button(interactive=False)  # always reset confirm btn after click
        return (status, new_issues_ack, new_step, step_complete_reset,
                btn, rows, progress, title)

    send_btn.click(
        fn=_chat_and_format,
        inputs=[textbox, chatbot, session_id,
                current_step_state, draft_categories, draft_families,
                draft_recipe_units, draft_inv_units],
        outputs=[chatbot, textbox,
                 draft_categories, draft_families, draft_recipe_units, draft_inv_units,
                 step_complete_state, confirm_btn, entity_table, progress_md, step_title_md],
    )

    confirm_btn.click(
        fn=_confirm_and_advance,
        inputs=[current_step_state, draft_categories, draft_families,
                draft_recipe_units, draft_inv_units, issues_acknowledged, session_id],
        outputs=[status_md, issues_acknowledged, current_step_state,
                 step_complete_state, confirm_btn, entity_table, progress_md, step_title_md],
    )
```

---

## `_data_store` Schema for `ConfigurationAgent` (reference)

```python
{
    "current_step":   "categories",   # str key written by _generate_prompt
    "categories":     [...],          # list[dict] — accumulated across turns
    "families":       [...],
    "recipe_units":   [...],
    "inventory_units": [...],
}
```

---

## Risks and Open Questions

### [OPEN] — Initial greeting with real session context
The `render()` function receives `session_id` as a `gr.State`, not a plain string — it's
not available at render time. The initial greeting cannot call `_load_configuration_context()`
directly at `gr.Chatbot(value=...)` init time.
**Greeting is level-aware (Level 1 vs 2/3):** Level 1 shows template preview inline;
Level 2/3 acknowledges operator experience and defers template to first agent turn.
**Suggested action:** Use a static Level 1 fallback greeting at render time. Add a
`gr.on("load", ...)` handler that reads the real session_id, calls
`_load_configuration_context()`, and updates `chatbot` with the correctly-leveled greeting
before the operator types anything.

### [OPEN] — `_init_section` called without a real session_id at render time
`render()` is called before the user's session is established. `current_step_state` cannot
be seeded with the correct resume index at `gr.State()` init time.
**Suggested action:** Set `current_step_state = gr.State(0)` as default. Add a
`gr.on("load", ...)` handler that reads the real session_id and updates `current_step_state`
and `progress_md` to the correct resume position.

### [RESOLVED] — `gr.Dataframe` column headers change per step
`entity_table` is initialized with `"categories"` columns. When the step advances, the
header set changes (`recipe_units` adds `symbol`; `inventory_units` adds `is_standard`).
**Resolution:** Return `gr.update(headers=_STEP_COLUMNS[step_key], value=rows)` (not plain
`rows`) from both `_chat_and_format` and `_confirm_and_advance` for the `entity_table` output.

---

### [OPEN] — `gr.on("load", ...)` inside a Tab context may not fire correctly
**Source:** Validation of subtask 9.3
**Problem:** The plan suggests `gr.on("load", ...)` inside `render()` to update the greeting
and resume step once the real session_id is available. In Gradio 4.x, load events added
inside a `with gr.Tab(...)` block fire on app load, not on tab switch. The Tab's `select`
event is the correct trigger for tab-activation logic, but `render()` does not have access
to the Tab object.
**Impact:** Level-aware greeting and resume-step detection may never fire; operator always
sees Level 1 fallback greeting and step 0 regardless of actual session state.
**Suggested action:** During 9.3 implementation, test whether `gr.on("load", ...)` fires
on tab switch. If not, either pass the Tab object into `render()` from `app.py` and wire
`tab.select`, or accept the static fallback greeting and step 0 as MVP behavior.

### [OPEN] — Sequential entity IDs (1, 2, 3…) collide across sessions in shared SQLite
**Source:** Validation of subtask 9.3
**Problem:** `save_entity_obj` uses `entity.id` as the DB primary key. The plan assigns IDs
starting from 1 per step save. A second session saving CategoryRecipe with id=1 silently
overwrites the first session's data.
**Impact:** In a multi-session or multi-restaurant context, confirmed configuration data is
overwritten without warning. Single-restaurant use is unaffected for MVP 0.1.
**Suggested action:** Acceptable for MVP 0.1 (one restaurant per DataLake). Add a note to
the Task 10 parent plan to revisit ID strategy before multi-tenant support.

---

## Deliverable Checklist

- [ ] Stub replaced with full `render()`
- [ ] `_load_configuration_context()` returns `restaurant_type_id`, `restaurant_type`, `restaurant_name`, `standardization_level` (Level 1 fallback)
- [ ] `_init_section()` returns correct resume index from `list_ids()`
- [ ] `_initial_greeting()` is a function, not a constant — called after context is loaded
- [ ] Sequential step UI: progress indicator, step title, `gr.Dataframe(interactive=False)`, confirm button, status markdown
- [ ] `_make_progress_md()` shows ✓ for completed steps, → for active step
- [ ] `_chat_and_format()` single-handler pattern — no `gr.State.change()`
- [ ] Confirm button disabled until `step_complete=True` from agent
- [ ] Per-step consistency check on first confirm click
- [ ] Final cross-entity check on first confirm click for step 3
- [ ] Two-click confirm flow: `issues_acknowledged` state gates the save
- [ ] `_save_step()` assigns sequential IDs starting from 1
- [ ] `data_lake.save_entity_obj()` called for each entity in the confirmed draft
- [ ] `issues_acknowledged` and `step_complete` reset after each successful save
- [ ] `current_step` advances after each save; stops at 3 (clamped for UI display)
- [ ] Non-standard `InventoryUnit` saved with `factor_to_base=1.0`
