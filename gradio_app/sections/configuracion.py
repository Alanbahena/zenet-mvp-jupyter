"""Configuración section — sequential 4-step configuration UI.

Guides the operator through confirming four entity lists:
  0. categories      → CategoryRecipe
  1. families        → FamilyInventory
  2. recipe_units    → RecipeUnit
  3. inventory_units → InventoryUnit

One step is visible at a time. The ConfigurationAgent drives the conversation;
the ConsistencyCheckAgent validates before each confirm. Entities are persisted
to DataLake only when the operator clicks Confirm.
"""
from __future__ import annotations

import gradio as gr

from core.agents.configuration_agent import ConfigurationAgent
from core.agents.consistency_check_agent import ConsistencyCheckAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import (
    DEFAULT_RESTAURANT_TYPES,
    CategoryRecipe,
    FamilyInventory,
    InventoryUnit,
    RecipeUnit,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_STEP_KEYS: list[str] = [
    "categories",
    "families",
    "recipe_units",
    "inventory_units",
]

# Entity type strings used by DataLake.list_ids() — parallel to _STEP_KEYS
_STEP_ENTITY_TYPES: list[str] = [
    "category_recipe",
    "family_inventory",
    "recipe_unit",
    "inventory_unit",
]

_STEP_TITLES: dict[str, str] = {
    "categories":      "Categorías de recetas",
    "families":        "Familias de inventario",
    "recipe_units":    "Unidades de receta",
    "inventory_units": "Unidades de inventario",
}

_STEP_DESCRIPTIONS: dict[str, str] = {
    "categories":      "agrupan tus recetas por tipo de servicio o turno",
    "families":        "agrupan tus ingredientes por tipo de producto",
    "recipe_units":    "son las unidades que aparecen en tus listas de ingredientes",
    "inventory_units": "son las unidades con las que compras y controlas tu stock",
}

# Dict keys used to extract values from entity dicts
_STEP_COLUMNS: dict[str, list[str]] = {
    "categories":      ["name", "description"],
    "families":        ["name", "description"],
    "recipe_units":    ["name", "symbol", "description"],
    "inventory_units": ["name", "symbol", "description"],
}

# Spanish display headers for gr.Dataframe — parallel to _STEP_COLUMNS
_STEP_COLUMN_LABELS: dict[str, list[str]] = {
    "categories":      ["Nombre", "Descripción"],
    "families":        ["Nombre", "Descripción"],
    "recipe_units":    ["Nombre", "Símbolo", "Descripción"],
    "inventory_units": ["Nombre", "Símbolo", "Descripción"],
}

# Column widths for gr.Dataframe per step
_STEP_COLUMN_WIDTHS: dict[str, list[str]] = {
    "categories":      ["35%", "65%"],
    "families":        ["35%", "65%"],
    "recipe_units":    ["30%", "10%", "60%"],
    "inventory_units": ["25%", "10%", "65%"],
}

_ENTITY_BUILDERS = {
    "categories": lambda i, e: CategoryRecipe(
        id=i,
        name=e["name"],
        description=e.get("description"),
    ),
    "families": lambda i, e: FamilyInventory(
        id=i,
        name=e["name"],
        description=e.get("description"),
    ),
    "recipe_units": lambda i, e: RecipeUnit(
        id=i,
        name=e["name"],
        symbol=e["symbol"],
        description=e.get("description"),
    ),
    "inventory_units": lambda i, e: InventoryUnit(
        id=i,
        name=e["name"],
        symbol=e["symbol"],
        is_standard=e.get("is_standard", False),
        factor_to_base=e.get("factor_to_base", 1.0),
        description=e.get("description"),
    ),
}

# ---------------------------------------------------------------------------
# Context and section init helpers
# ---------------------------------------------------------------------------

def _load_configuration_context(data_lake, session_id: str) -> dict:
    """Load restaurant type and classification level from DataLake for this session."""
    entity_id = abs(hash(session_id)) % (2**31 - 1)

    restaurant_name = ""
    restaurant_type = ""
    restaurant_type_id = 1

    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if restaurant_data:
        restaurant_name = restaurant_data.get("name", "")
        type_id = restaurant_data.get("restaurant_type_id")
        if type_id is not None:
            restaurant_type_id = type_id
            type_map = {t.id: t.name for t in DEFAULT_RESTAURANT_TYPES}
            restaurant_type = type_map.get(type_id, "")

    standardization_level = 1
    classification_data = data_lake.load_entity("classification", entity_id)
    if classification_data:
        level = classification_data.get("standardization_level")
        if level is not None:
            standardization_level = level

    return {
        "restaurant_type_id":    restaurant_type_id,
        "restaurant_type":       restaurant_type,
        "restaurant_name":       restaurant_name,
        "standardization_level": standardization_level,
    }


def _init_section(data_lake) -> int:
    """Return the index of the first incomplete step (0-3), or 4 if all complete."""
    for idx, entity_type in enumerate(_STEP_ENTITY_TYPES):
        if not data_lake.list_entity_ids(entity_type):
            return idx
    return 4


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def _initial_greeting(
    restaurant_type: str,
    template_preview: str,
    standardization_level: int,
) -> list[dict]:
    """Build the level-aware initial greeting for the chatbot."""
    if standardization_level == 1:
        if template_preview:
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
                "Vamos a construirlo juntos desde cero. "
                "Empecemos con las categorías de recetas. ¿Listo?"
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


def _make_progress_md(current_step: int) -> str:
    """Build the progress indicator markdown string."""
    parts = []
    for i, key in enumerate(_STEP_KEYS):
        title = _STEP_TITLES[key]
        if i < current_step:
            parts.append(f"**{title} ✓**")
        elif i == current_step:
            parts.append(f"**→ {title}**")
        else:
            parts.append(title)
    return " · ".join(parts)


def _draft_to_rows(draft: list[dict], step_key: str) -> list[list]:
    """Convert a list of entity dicts to rows for gr.Dataframe."""
    if not draft:
        return []
    columns = _STEP_COLUMNS[step_key]
    return [[e.get(col, "") for col in columns] for e in draft]


# ---------------------------------------------------------------------------
# Persistence helper
# ---------------------------------------------------------------------------

def _save_step(data_lake, step_key: str, draft: list[dict]) -> None:
    """Assign sequential IDs and persist all entities for the given step."""
    builder = _ENTITY_BUILDERS[step_key]
    for idx, entity_dict in enumerate(draft, start=1):
        entity = builder(idx, entity_dict)
        data_lake.save_entity_obj(entity)


# ---------------------------------------------------------------------------
# Chat and confirm handlers
# ---------------------------------------------------------------------------

def _make_chat_fn(provider, data_lake, initial_greeting_text: str):
    def chat_fn(
        message, history, session_id, current_step,
        draft_cats, draft_fams, draft_ru, draft_iu,
    ):
        if not session_id:
            history = list(history)
            history.append({
                "role": "assistant",
                "content": "Sesión no iniciada. Recarga la página.",
            })
            return history, "", draft_cats, draft_fams, draft_ru, draft_iu, False

        if not (message or "").strip():
            return history, "", draft_cats, draft_fams, draft_ru, draft_iu, False

        if current_step >= len(_STEP_KEYS):
            history = list(history)
            history.append({
                "role": "assistant",
                "content": "La configuración ya está completa. Puedes continuar con Alineamiento.",
            })
            return history, "", draft_cats, draft_fams, draft_ru, draft_iu, False

        agent = create_agent(ConfigurationAgent, provider=provider, name="configuration_agent")
        agent.load_state(data_lake, session_id=f"configuration_agent_{session_id}")

        # On the first turn inject the static greeting into memory so the agent
        # knows it already greeted the operator and continues naturally.
        if agent.memory.message_count == 0:
            agent.memory.add_assistant(initial_greeting_text)

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

        drafts = [draft_cats, draft_fams, draft_ru, draft_iu]
        if entities is not None:
            drafts[current_step] = entities

        return history, "", drafts[0], drafts[1], drafts[2], drafts[3], step_complete

    return chat_fn


def _make_confirm_fn(data_lake):
    def confirm_fn(
        current_step, draft_cats, draft_fams, draft_ru, draft_iu,
        issues_ack, session_id,
    ):
        if not session_id:
            return "Sesión no iniciada. Recarga la página.", False, current_step, False

        if current_step >= len(_STEP_KEYS):
            return "La configuración ya está completa.", False, current_step, False

        step_key = _STEP_KEYS[current_step]
        drafts = [draft_cats, draft_fams, draft_ru, draft_iu]
        current_draft = drafts[current_step]

        # Second click: operator has acknowledged issues — save regardless
        if issues_ack:
            _save_step(data_lake, step_key, current_draft)
            new_step = current_step + 1
            if new_step > 3:
                status = f"**{_STEP_TITLES[step_key]}** guardadas. Configuración completa — ya puedes continuar con Alineamiento."
            else:
                next_key = _STEP_KEYS[new_step]
                status = f"**{_STEP_TITLES[step_key]}** guardadas. Siguiente: **{_STEP_TITLES[next_key]}** — {_STEP_DESCRIPTIONS[next_key]}."
            return status, False, new_step, False

        # First click: run the appropriate consistency check
        ctx = _load_configuration_context(data_lake, session_id)
        restaurant_type = ctx.get("restaurant_type", "")

        check_agent = create_agent(
            ConsistencyCheckAgent, provider=ClaudeProvider(), name="consistency_check"
        )

        if current_step == 3:
            # Final step: cross-entity check across all four lists
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

        if not looks_good:
            issues_md = (
                "**Advertencias antes de confirmar:**\n"
                + "\n".join(f"- {i}" for i in issues)
                + "\n\nHaz clic en **Confirmar** de nuevo para guardar de todas formas."
            )
            return issues_md, True, current_step, False

        # No issues: save immediately
        _save_step(data_lake, step_key, current_draft)
        new_step = current_step + 1
        if new_step > 3:
            status = f"**{_STEP_TITLES[step_key]}** guardadas. Configuración completa — ya puedes continuar con Alineamiento."
        else:
            next_key = _STEP_KEYS[new_step]
            status = f"**{_STEP_TITLES[step_key]}** guardadas. Siguiente: **{_STEP_TITLES[next_key]}** — {_STEP_DESCRIPTIONS[next_key]}."
        return status, False, new_step, False

    return confirm_fn


# ---------------------------------------------------------------------------
# Section entry point
# ---------------------------------------------------------------------------

def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()

    # --- State ---
    current_step_state  = gr.State(0)
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
            chatbot = gr.Chatbot(
                label="Asistente Zenet",
                height="60vh",
                value=_initial_greeting("tu restaurante", "", 1),
            )
            textbox  = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
            send_btn = gr.Button("Enviar")

        with gr.Column(scale=1):
            progress_md   = gr.Markdown(_make_progress_md(0))
            step_title_md = gr.Markdown(f"### {_STEP_TITLES['categories']}")
            entity_table  = gr.Dataframe(
                headers=_STEP_COLUMN_LABELS["categories"],
                column_widths=_STEP_COLUMN_WIDTHS["categories"],
                interactive=False,
                label="Entidades propuestas",
            )
            confirm_btn = gr.Button("Confirmar y continuar", interactive=False)
            status_md   = gr.Markdown("")

    # --- Wiring ---
    greeting_text = _initial_greeting("tu restaurante", "", 1)[0]["content"]
    chat_fn    = _make_chat_fn(provider, data_lake, greeting_text)
    confirm_fn = _make_confirm_fn(data_lake)

    def _chat_and_format(
        message, history, sid,
        current_step, draft_cats, draft_fams, draft_ru, draft_iu,
    ):
        history, text, d_cats, d_fams, d_ru, d_iu, s_complete = chat_fn(
            message, history, sid, current_step,
            draft_cats, draft_fams, draft_ru, draft_iu,
        )
        step_key = _STEP_KEYS[min(current_step, len(_STEP_KEYS) - 1)]
        drafts = [d_cats, d_fams, d_ru, d_iu]
        rows = _draft_to_rows(drafts[min(current_step, len(_STEP_KEYS) - 1)], step_key)
        return (
            history,
            text,
            d_cats,
            d_fams,
            d_ru,
            d_iu,
            s_complete,
            gr.update(interactive=s_complete),
            gr.update(headers=_STEP_COLUMN_LABELS[step_key], column_widths=_STEP_COLUMN_WIDTHS[step_key], value=rows),
            _make_progress_md(current_step),
            f"### {_STEP_TITLES[step_key]}",
        )

    def _confirm_and_advance(
        history, current_step, draft_cats, draft_fams, draft_ru, draft_iu,
        issues_ack, sid,
    ):
        # Show loading indicator only on first click (when consistency check will run)
        if not issues_ack and sid and current_step < len(_STEP_KEYS):
            yield (
                gr.update(), "Verificando consistencia...",
                gr.update(), gr.update(), gr.update(),
                gr.update(interactive=False),
                gr.update(), gr.update(), gr.update(),
                gr.update(), gr.update(), gr.update(), gr.update(),
            )

        status, new_issues_ack, new_step, step_complete_reset = confirm_fn(
            current_step, draft_cats, draft_fams, draft_ru, draft_iu, issues_ack, sid,
        )
        new_step_clamped = min(new_step, len(_STEP_KEYS) - 1)
        step_key = _STEP_KEYS[new_step_clamped]
        drafts = [draft_cats, draft_fams, draft_ru, draft_iu]

        new_history = list(history)
        new_step_complete = step_complete_reset

        if new_step > current_step:
            if new_step >= len(_STEP_KEYS):
                new_history.append({
                    "role": "assistant",
                    "content": "¡Listo! Configuración completa. Ya puedes continuar con Alineamiento.",
                })
            else:
                # Fire agent transition — only the assistant reply is added, no user message shown
                agent = create_agent(
                    ConfigurationAgent, provider=provider, name="configuration_agent"
                )
                agent.load_state(data_lake, session_id=f"configuration_agent_{sid}")
                ctx = _load_configuration_context(data_lake, sid)
                ctx["current_step"] = _STEP_KEYS[new_step_clamped]
                try:
                    result = agent.run(
                        input_data={"user_message": "__confirmed__"}, context=ctx
                    )
                    reply = result["reply"]
                    entities = result.get("entities")
                    if result.get("step_complete") is not None:
                        new_step_complete = bool(result["step_complete"])
                except Exception:
                    reply = None
                    entities = None
                agent.save_state(data_lake, session_id=f"configuration_agent_{sid}")
                if reply:
                    new_history.append({"role": "assistant", "content": reply})
                if entities is not None:
                    drafts[new_step_clamped] = entities

        rows = _draft_to_rows(drafts[new_step_clamped], step_key)

        yield (
            new_history,
            status,
            new_issues_ack,
            new_step,
            new_step_complete,
            gr.update(interactive=new_step_complete),
            gr.update(headers=_STEP_COLUMN_LABELS[step_key], column_widths=_STEP_COLUMN_WIDTHS[step_key], value=rows),
            _make_progress_md(new_step),
            f"### {_STEP_TITLES[step_key]}",
            drafts[0], drafts[1], drafts[2], drafts[3],
        )

    send_btn.click(
        fn=_chat_and_format,
        inputs=[
            textbox, chatbot, session_id,
            current_step_state,
            draft_categories, draft_families, draft_recipe_units, draft_inv_units,
        ],
        outputs=[
            chatbot, textbox,
            draft_categories, draft_families, draft_recipe_units, draft_inv_units,
            step_complete_state, confirm_btn, entity_table, progress_md, step_title_md,
        ],
    )

    confirm_btn.click(
        fn=_confirm_and_advance,
        inputs=[
            chatbot, current_step_state,
            draft_categories, draft_families, draft_recipe_units, draft_inv_units,
            issues_acknowledged, session_id,
        ],
        outputs=[
            chatbot, status_md, issues_acknowledged, current_step_state,
            step_complete_state, confirm_btn, entity_table, progress_md, step_title_md,
            draft_categories, draft_families, draft_recipe_units, draft_inv_units,
        ],
        show_progress="hidden",
    )
