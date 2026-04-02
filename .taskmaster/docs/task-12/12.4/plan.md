# Subtask 12.4 — Gradio wiring: two-state UI, persistent agent sidebar, tab assembly

## Goal

Replace the `render()` stub in `gradio_app/sections/manual_operativo.py` with the full
two-state Gradio UI: State 1 (generate button) → State 2 (four-tab manual + persistent
agent sidebar), so the operator can generate and interact with their operational manual.

- **12.2 + 12.3 delivered:** All four Markdown builder functions (`_build_resumen_md`,
  `_build_mi_restaurante_md`, `_build_recetas_md`, `_build_inventario_md`) and
  `_build_manual_context` — pure functions ready to be called from `generate_fn`.
- **12.5 needs from 12.4:** A complete, working `render()` with all Gradio components
  instantiated, so 12.5 can write tests against the builder functions and agent behavior.

---

## Files to Modify / Create

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/manual_operativo.py` | Modify | Replace `render()` stub with full two-state Gradio UI + `generate_fn` + `chat_fn` |

No other files.

---

## Dependencies

- Subtasks 12.1, 12.2, 12.3 done — all builders and `_build_manual_context` in place.
- `gradio_app/components.py` — `render_chat_panel(chat_fn, session_id, data_lake_ref)` exists.
- `core.agents.ManualOperativoAgent` — exists, re-exported from `core`.
- `core.agents.utils.create_agent(agent_class, *, provider, **kwargs)` — `provider` is keyword-only.
- `core.ai.providers.ClaudeProvider` — exists.
- `gradio_app.session.stable_entity_id` — already imported in file.
- `ANTHROPIC_API_KEY` in `.env`.

---

## Key design decisions

| Decision | Rationale |
|----------|-----------|
| Two-state UI via `gr.Column(visible=False/True)` | Button ceremony marks the operator's transition from data entry to "I have a system"; avoids loading on tab open |
| `gr.Column(scale=7)` tabs + `gr.Column(scale=3)` agent | Agent always visible beside the manual; operator never loses their place to ask a question |
| `generate_fn` rebuilds registries independently from `_build_manual_context` | Keeps `_build_manual_context` focused on agent context string; avoids coupling the two code paths |
| "Regenerar Manual" re-calls content portion of `generate_fn` in-place | Handles the case where the operator returns to earlier sections and updates data; no page reload |
| `chat_fn` calls `_build_manual_context` fresh each turn | Agent context stays current; cost is acceptable at Phase A data volume |

---

## Implementation steps

### 1. Add missing imports to `manual_operativo.py`

Add to the existing import block at the top of the file (check for duplicates first):

```python
from gradio_app.components import render_chat_panel
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.serialization import restaurant_from_dict  # already present
```

`render_chat_panel` and `create_agent` and `ClaudeProvider` are not currently imported —
add them. All serialization imports are already in place from 12.1.

### 2. Define `_make_content(data_lake, sid)` private helper

A private function that loads all DataLake entities, builds registries, calls all four
builders, and returns the four Markdown strings. Reused by both `generate_fn` and
`regen_fn` to avoid duplicating the loading logic.

```python
def _make_content(data_lake, sid: str) -> tuple[str, str, str, str]:
    """Load entities, build registries, return (resumen, mi_rest, recetas, inventario) Markdown strings.

    Returns placeholder strings for all four tabs if no restaurant entity exists.
    """
    entity_id = stable_entity_id(sid)

    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if not restaurant_data:
        placeholder = "_Sin datos de restaurante. Completa las secciones anteriores primero._"
        return placeholder, placeholder, placeholder, placeholder

    restaurant = restaurant_from_dict(restaurant_data)
    user_data = data_lake.load_entity("user", entity_id) or {}
    classification_data = data_lake.load_entity("classification", entity_id) or {}

    # Load all entity lists
    recipe_units = [
        recipe_unit_from_dict(data_lake.load_entity("recipe_unit", uid))
        for uid in data_lake.list_entity_ids("recipe_unit")
    ]
    inventory_units = [
        inventory_unit_from_dict(data_lake.load_entity("inventory_unit", uid))
        for uid in data_lake.list_entity_ids("inventory_unit")
    ]
    categories = [
        category_recipe_from_dict(data_lake.load_entity("category_recipe", cid))
        for cid in data_lake.list_entity_ids("category_recipe")
    ]
    families = [
        family_inventory_from_dict(data_lake.load_entity("family_inventory", fid))
        for fid in data_lake.list_entity_ids("family_inventory")
    ]
    recipes = [
        recipe_from_dict(data_lake.load_entity("recipe", rid))
        for rid in data_lake.list_entity_ids("recipe")
    ]
    items = [
        inventory_item_from_dict(data_lake.load_entity("inventory_item", iid))
        for iid in data_lake.list_entity_ids("inventory_item")
    ]

    # Build registries
    recipe_unit_registry = RecipeUnitRegistry()
    for u in recipe_units:
        recipe_unit_registry.add(u)

    inventory_unit_registry = InventoryUnitRegistry()
    for u in inventory_units:
        inventory_unit_registry.add(u)

    category_registry = CategoryRecipeRegistry()
    for c in categories:
        category_registry.add(c)

    family_registry = FamilyInventoryRegistry()
    for f in families:
        family_registry.add(f)

    item_registry = InventoryItemRegistry()
    for item in items:
        item_registry.add(item)

    conversion_table = RecipeUnitConversionRegistry()
    for cid in data_lake.list_entity_ids("recipe_unit_conversion"):
        raw = data_lake.load_entity("recipe_unit_conversion", cid)
        if raw:
            key, entry = recipe_unit_conversion_from_dict(raw)
            conversion_table.add(
                key.recipe_unit_id,
                entry.quantity,
                entry.base_unit_id,
                family_id=key.family_id,
                inventory_item_id=key.inventory_item_id,
                source=entry.source,
            )

    # Compute KPI report
    report = compute_readiness_report(
        restaurant,
        recipes=recipes,
        recipe_unit_registry=recipe_unit_registry,
        inventory_unit_registry=inventory_unit_registry,
        category_recipe_registry=category_registry,
        family_inventory_registry=family_registry,
        inventory_item_registry=item_registry,
        conversion_table=conversion_table,
    )

    resumen = _build_resumen_md(
        report,
        recipe_unit_registry,
        inventory_unit_registry,
        item_registry,
        recipes=recipes,
        items=items,
    )
    mi_rest = _build_mi_restaurante_md(
        restaurant,
        user_data,
        classification_data,
        recipe_units=recipe_units,
        inventory_units=inventory_units,
        categories=categories,
        families=families,
        recipes=recipes,
        items=items,
    )
    recetas = _build_recetas_md(
        recipes, recipe_unit_registry, item_registry,
        category_registry, inventory_unit_registry, conversion_table, family_registry,
    )
    inventario = _build_inventario_md(items, inventory_unit_registry, family_registry)

    return resumen, mi_rest, recetas, inventario
```

Place `_make_content` after `_build_inventario_md` and before `_build_manual_context`.

### 3. Replace `render()` stub

The current stub (line 418–420):
```python
def render(session_id: gr.State, data_lake) -> None:
    """Stub — replaced by Task 12."""
    gr.Markdown("### Manual operativo\nPendiente — Task 12.")
```

Replace entirely with:

```python
def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()
    agent = create_agent(ManualOperativoAgent, provider=provider, name="manual_operativo")

    def chat_fn(message: str, history: list, sid: str) -> tuple[list, str]:
        context = {"manual_context": _build_manual_context(data_lake, sid)}
        result = agent.run(input_data={"user_message": message}, context=context)
        reply = result.get("reply", "")
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    def generate_fn(sid: str):
        resumen, mi_rest, recetas, inventario = _make_content(data_lake, sid)
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            resumen,
            mi_rest,
            recetas,
            inventario,
        )

    def regen_fn(sid: str):
        return _make_content(data_lake, sid)

    # ------------------------------------------------------------------
    # State 1 — empty state: single generate button
    # ------------------------------------------------------------------
    with gr.Column() as state1_col:
        gr.Markdown("### Manual Operativo")
        gr.Markdown(
            "Genera tu manual operativo una vez que hayas completado las secciones anteriores."
        )
        generate_btn = gr.Button("Generar Manual Operativo", variant="primary")

    # ------------------------------------------------------------------
    # State 2 — generated state (hidden until generate_btn clicked)
    # ------------------------------------------------------------------
    with gr.Column(visible=False) as state2_col:
        regen_btn = gr.Button("Regenerar Manual")
        with gr.Row():
            with gr.Column(scale=7):
                with gr.Tabs():
                    with gr.Tab("Resumen"):
                        resumen_md = gr.Markdown("")
                    with gr.Tab("Mi Restaurante"):
                        mi_rest_md = gr.Markdown("")
                    with gr.Tab("Recetas"):
                        recetas_md = gr.Markdown("")
                    with gr.Tab("Inventario"):
                        inventario_md = gr.Markdown("")
            with gr.Column(scale=3):
                gr.Markdown("### Asistente Operativo")
                render_chat_panel(chat_fn, session_id, data_lake)

    generate_btn.click(
        fn=generate_fn,
        inputs=[session_id],
        outputs=[state1_col, state2_col, resumen_md, mi_rest_md, recetas_md, inventario_md],
    )
    regen_btn.click(
        fn=regen_fn,
        inputs=[session_id],
        outputs=[resumen_md, mi_rest_md, recetas_md, inventario_md],
    )
```

### 4. Verify `app.py` needs no changes

`gradio_app/app.py` line 29 already calls `manual_operativo.render(session_id, data_lake)`.
No modification needed.

---

## Out of scope

- No changes to `core/`, `tests/`, `app.py`, `components.py`, or any other section
- No LangGraph integration
- No PDF export
- No real-time stock deduction
- No multi-session support

---

## Test coverage

No new unit tests in this subtask. Subtask 12.5 should add:
- `test_generate_fn_returns_six_tuple` — `generate_fn` with empty DataLake returns 6 values,
  first two are `gr.update` objects, last four are strings.

Live tests deferred to 12.5 (`test_manual_operativo_agent_qa_live`,
`test_manual_operativo_agent_deduction_live`).

---

## Risks and open questions

- `gr.Column` as `.click()` output: supported in Gradio 4+ (project uses Gradio 6.x — safe).
- `render_chat_panel` returns `None` (confirmed from `components.py:152`) — called purely
  for side effects inside the active `gr.Column` context. No return value needed.
- `create_agent` signature: `create_agent(agent_class, *, provider, **kwargs)` —
  `provider` is keyword-only (confirmed from `core/agents/utils.py:42-47`).
- `_make_content` loads entities independently from `_build_manual_context` — intentional
  per plan (two decoupled code paths). Both run on button click, not on section load.

---

## Deliverable checklist

`gradio_app/sections/manual_operativo.py`:
- [ ] `render_chat_panel`, `create_agent`, `ClaudeProvider` imported
- [ ] `_make_content(data_lake, sid) -> tuple[str, str, str, str]` added (loads entities, builds registries, calls all four builders)
- [ ] `_make_content` handles missing restaurant entity (returns placeholder strings, no crash)
- [ ] `render()` stub replaced with full implementation
- [ ] State 1: `gr.Column` with "Generar Manual Operativo" `gr.Button(variant="primary")`
- [ ] State 2: `gr.Column(visible=False)` revealed on button click
- [ ] State 2 layout: `gr.Row` with `gr.Column(scale=7)` tabs + `gr.Column(scale=3)` agent sidebar
- [ ] 4 tabs: Resumen, Mi Restaurante, Recetas, Inventario — each backed by a `gr.Markdown`
- [ ] `generate_btn.click` outputs: `[state1_col, state2_col, resumen_md, mi_rest_md, recetas_md, inventario_md]`
- [ ] `regen_btn.click` outputs: `[resumen_md, mi_rest_md, recetas_md, inventario_md]` (no visibility toggle)
- [ ] `chat_fn` closure defined inside `render()`, captures `agent` and `data_lake`
- [ ] `render_chat_panel(chat_fn, session_id, data_lake)` called inside `gr.Column(scale=3)` context
- [ ] `app.py` unchanged (already wired correctly)
