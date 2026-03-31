"""Estructura section — inventory structuring UI.

Guides the operator through 4 phases:
  1. enrich_perecederos     — propose units/family for base perishable items
  2. add_perecederos        — capture additional perishable items
  3. enrich_no_perecederos  — same for base non-perishable items
  4. add_no_perecederos     — capture additional non-perishable items

Each phase uses a dedicated StructuringAgent session (separate memory/data_store).
No LangGraph — StructuringAgent is called directly per turn.
"""
from __future__ import annotations

from typing import Any

import gradio as gr

from core.agents.structuring_agent import StructuringAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES, InventoryItem
from core.domain.serialization import inventory_item_to_dict
from gradio_app.sections.alineamiento import _extract_file_text
from gradio_app.session import stable_entity_id

_INVENTORY_CATEGORY_IDS = {"Perecedero": 1, "No perecedero": 2}

_PHASE_SEQUENCE = [
    "enrich_perecederos",
    "add_perecederos",
    "enrich_no_perecederos",
    "add_no_perecederos",
]

_PHASE_CATEGORY: dict[str, str] = {
    "enrich_perecederos":    "Perecedero",
    "add_perecederos":       "Perecedero",
    "enrich_no_perecederos": "No perecedero",
    "add_no_perecederos":    "No perecedero",
}

_PHASE_MODE: dict[str, str] = {
    "enrich_perecederos":    "enrich",
    "add_perecederos":       "add",
    "enrich_no_perecederos": "enrich",
    "add_no_perecederos":    "add",
}

_PHASE_LABEL: dict[str, str] = {
    "enrich_perecederos":    "### Perecederos — Base",
    "add_perecederos":       "### Perecederos — Adicionales",
    "enrich_no_perecederos": "### No Perecederos — Base",
    "add_no_perecederos":    "### No Perecederos — Adicionales",
}


# ---------------------------------------------------------------------------
# Phase helpers
# ---------------------------------------------------------------------------

def _agent_session_key(session_id: str, phase: str) -> str:
    return f"structuring_{phase}_{session_id}"


def _count_items_by_category(data_lake: Any, category_id: int) -> int:
    return sum(
        1
        for eid in data_lake.list_entity_ids("inventory_item")
        if (data_lake.load_entity("inventory_item", eid) or {}).get("category_id") == category_id
    )


def _phase_greeting(phase: str, data_lake: Any) -> str:
    if phase == "enrich_perecederos":
        count = _count_items_by_category(data_lake, 1)
        return (
            f"Vamos a estructurar tu inventario. Comenzaremos con los {count} artículo(s) "
            "perecederos de tu inventario base. Cuando estés listo, dímelo y te haré una "
            "propuesta de unidades y familias para cada uno."
        )
    if phase == "add_perecederos":
        return (
            "¿Tienes artículos perecederos adicionales que no provienen de tus recetas? "
            "Puedes describírmelos o subir un archivo. "
            'Si no tienes más, di "listo" para continuar.'
        )
    if phase == "enrich_no_perecederos":
        count = _count_items_by_category(data_lake, 2)
        return (
            f"Perfecto, ahora pasamos a los no perecederos. Tienes {count} artículo(s) "
            "en tu inventario base. Cuando estés listo, dímelo y te haré una propuesta."
        )
    if phase == "add_no_perecederos":
        return (
            "¿Tienes artículos no perecederos adicionales? "
            "Puedes describírmelos o subir un archivo. "
            'Si no tienes más, di "listo" para continuar.'
        )
    return ""


# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

def _load_structuring_context(
    data_lake: Any,
    session_id: str,
    category: str = "Perecedero",
) -> dict:
    """Load all entities needed by StructuringAgent._generate_prompt."""
    entity_id = stable_entity_id(session_id)

    restaurant_name = ""
    restaurant_type = ""
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if restaurant_data:
        restaurant_name = restaurant_data.get("name", "")
        type_id = restaurant_data.get("restaurant_type_id")
        if type_id is not None:
            type_map = {t.id: t.name for t in DEFAULT_RESTAURANT_TYPES}
            restaurant_type = type_map.get(type_id, "")

    restaurant_description = ""
    classification_data = data_lake.load_entity("classification", entity_id)
    if classification_data:
        restaurant_description = classification_data.get("restaurant_description", "")

    category_id = _INVENTORY_CATEGORY_IDS.get(category, 1)
    inventory_items: list[str] = []
    for eid in data_lake.list_entity_ids("inventory_item"):
        e = data_lake.load_entity("inventory_item", eid)
        if e and e.get("category_id") == category_id:
            inventory_items.append(e["name"])

    families: list[str] = []
    for eid in data_lake.list_entity_ids("family_inventory"):
        e = data_lake.load_entity("family_inventory", eid)
        if e:
            families.append(e["name"])

    inventory_units: list[str] = []
    for eid in data_lake.list_entity_ids("inventory_unit"):
        e = data_lake.load_entity("inventory_unit", eid)
        if e:
            inventory_units.append(e["symbol"])

    return {
        "restaurant_name":        restaurant_name,
        "restaurant_type":        restaurant_type,
        "restaurant_description": restaurant_description,
        "inventory_items":        inventory_items,
        "families":               families,
        "inventory_units":        inventory_units,
        "category":               category,
        "data_lake":              data_lake,
        "session_id":             session_id,
    }


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _proposals_to_rows(proposals: list[dict]) -> list[list]:
    """Map proposal dicts to table rows (6 columns, positional)."""
    return [
        [
            p.get("name", ""),
            p.get("purchase_unit_symbol", ""),
            p.get("stock_unit_symbol", ""),
            p.get("purchase_to_stock_factor") if p.get("purchase_to_stock_factor") is not None else "",
            p.get("family_name") or "",
            p.get("category_name", ""),
        ]
        for p in (proposals or [])
    ]


# ---------------------------------------------------------------------------
# Chat handler
# ---------------------------------------------------------------------------

def _make_chat_fn(provider: Any, data_lake: Any):
    def chat_fn(
        message: str,
        history: list,
        session_id: str,
        recipe_source: str,
        phase: str,
    ):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, "", [], False

        if not (message or "").strip():
            return history, "", [], False

        if phase not in _PHASE_SEQUENCE:
            return history, "", [], False

        category  = _PHASE_CATEGORY[phase]
        mode      = _PHASE_MODE[phase]
        agent_key = _agent_session_key(session_id, phase)

        agent = create_agent(StructuringAgent, provider=provider, name="structuring_agent")
        agent.load_state(data_lake, session_id=agent_key)

        greeting = _phase_greeting(phase, data_lake)
        if not agent.memory.get_messages():
            agent.memory.add_assistant(greeting)

        ctx = _load_structuring_context(data_lake, session_id, category=category)

        try:
            result = agent.run(
                input_data={
                    "user_message":  message,
                    "recipe_source": recipe_source,
                    "category":      category,
                    "phase":         mode,
                },
                context=ctx,
            )
            reply         = result["reply"]
            proposals     = result.get("proposals") or []
            gap_questions = result.get("gap_questions") or []

            if mode == "enrich":
                # Enrich phase: confirm only when proposals exist and no pending questions
                ready = bool(proposals) and not gap_questions
            else:
                # Add phase: operator can confirm even with 0 new items
                ready = not gap_questions
        except Exception:
            reply         = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
            proposals     = []
            ready         = False

        agent.save_state(data_lake, session_id=agent_key)

        history = list(history)
        history.append({"role": "user",      "content": message})
        history.append({"role": "assistant", "content": reply})

        return history, "", proposals, ready

    return chat_fn


# ---------------------------------------------------------------------------
# Confirm handler
# ---------------------------------------------------------------------------

def _make_confirm_fn(data_lake: Any):
    def confirm_fn(
        proposals_rows,
        session_id: str,
        current_category: str,
    ):
        # gr.Dataframe passes a pandas DataFrame — normalize to list[list]
        if hasattr(proposals_rows, "values"):
            rows: list = proposals_rows.values.tolist()
        else:
            rows = list(proposals_rows or [])

        if not session_id:
            yield "Sesión no iniciada.", False
            return

        yield "Guardando...", False

        try:
            # Build lookup maps
            iu_symbol_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("inventory_unit"):
                e = data_lake.load_entity("inventory_unit", eid)
                if e:
                    iu_symbol_to_id[e["symbol"]] = int(eid)

            existing_item_name_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("inventory_item"):
                e = data_lake.load_entity("inventory_item", eid)
                if e:
                    existing_item_name_to_id[e["name"]] = int(eid)

            family_name_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("family_inventory"):
                e = data_lake.load_entity("family_inventory", eid)
                if e:
                    family_name_to_id[e["name"]] = int(eid)

            existing_item_ids = [int(i) for i in data_lake.list_entity_ids("inventory_item")]
            next_item_id = max(existing_item_ids, default=0) + 1

            def _resolve_unit_id(symbol: str) -> int:
                """Return existing unit ID or create a new non-standard unit."""
                if symbol in iu_symbol_to_id:
                    return iu_symbol_to_id[symbol]
                existing_unit_ids = data_lake.list_entity_ids("inventory_unit")
                new_id = max((int(i) for i in existing_unit_ids), default=0) + 1
                data_lake.save_entity("inventory_unit", new_id, {
                    "id":          new_id,
                    "name":        symbol,
                    "symbol":      symbol,
                    "description": None,
                    "base_unit_id": None,
                    "factor_to_base": 1.0,
                    "is_standard": False,
                })
                iu_symbol_to_id[symbol] = new_id
                return new_id

            count = 0
            for row in rows:
                if not row or not row[0]:
                    continue
                # Columns: [name, purchase_sym, stock_sym, factor, family_name, cat_name]
                name         = str(row[0]).strip()
                purchase_sym = str(row[1]).strip() if len(row) > 1 and row[1] else "pza"
                stock_sym    = str(row[2]).strip() if len(row) > 2 and row[2] else "pza"
                raw_factor   = row[3] if len(row) > 3 else None
                family_name  = str(row[4]).strip() if len(row) > 4 and row[4] else None
                cat_name     = str(row[5]).strip() if len(row) > 5 and row[5] else current_category

                if not name:
                    continue

                try:
                    factor = float(raw_factor) if raw_factor not in (None, "", "None") else 1.0
                except (ValueError, TypeError):
                    factor = 1.0

                stock_unit_id    = _resolve_unit_id(stock_sym)
                purchase_unit_id = _resolve_unit_id(purchase_sym)
                family_id        = family_name_to_id.get(family_name) if family_name else None
                category_id      = _INVENTORY_CATEGORY_IDS.get(
                    cat_name, _INVENTORY_CATEGORY_IDS[current_category]
                )

                if name in existing_item_name_to_id:
                    # UPDATE — enrich existing shell, preserve id + name
                    item_id  = existing_item_name_to_id[name]
                    existing = data_lake.load_entity("inventory_item", item_id) or {}
                    enriched = dict(existing)
                    enriched.update({
                        "stock_unit_id":            stock_unit_id,
                        "purchase_unit_id":         purchase_unit_id,
                        "purchase_to_stock_factor": factor,
                        "family_id":                family_id,
                        "category_id":              category_id,
                    })
                    data_lake.save_entity("inventory_item", item_id, enriched)
                else:
                    # INSERT — new item not in base inventory
                    item = InventoryItem(
                        id=next_item_id,
                        name=name,
                        stock_unit_id=stock_unit_id,
                        purchase_unit_id=purchase_unit_id,
                        purchase_to_stock_factor=factor,
                        category_id=category_id,
                        family_id=family_id,
                    )
                    data_lake.save_entity(
                        "inventory_item", next_item_id, inventory_item_to_dict(item)
                    )
                    existing_item_name_to_id[name] = next_item_id
                    next_item_id += 1

                count += 1

            yield f"{count} artículo(s) guardado(s) correctamente.", True

        except Exception as exc:
            yield f"Error al guardar: {exc}", False

    return confirm_fn


# ---------------------------------------------------------------------------
# Section entry point
# ---------------------------------------------------------------------------

def render(session_id: gr.State, data_lake: Any) -> None:
    provider = ClaudeProvider()

    initial_greeting  = _phase_greeting("enrich_perecederos", data_lake)
    initial_history   = [{"role": "assistant", "content": initial_greeting}]

    # State
    phase_state         = gr.State("enrich_perecederos")
    proposals_state     = gr.State([])
    recipe_source_state = gr.State("conversation")

    # Layout
    with gr.Row():
        # LEFT — chat
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de estructuración")
            chatbot = gr.Chatbot(
                label="Asistente Zenet",
                height="60vh",
                value=initial_history,
            )
            textbox = gr.Textbox(
                placeholder="Escribe tu mensaje...",
                show_label=False,
                lines=3,
                max_lines=3,
            )
            send_btn    = gr.Button("Enviar")
            file_upload = gr.File(
                label="Subir archivo de inventario",
                file_types=[".pdf", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".webp"],
            )

        # RIGHT — table
        with gr.Column(scale=1):
            phase_md    = gr.Markdown(_PHASE_LABEL["enrich_perecederos"])
            table       = gr.Dataframe(
                headers=["Artículo", "Compra", "Inventario", "Factor", "Familia", "Categoría"],
                interactive=True,
                label="Propuesta de inventario",
            )
            confirm_btn = gr.Button("Confirmar y guardar", interactive=False)
            status_md   = gr.Markdown("")

    # Handlers
    chat_fn    = _make_chat_fn(provider, data_lake)
    confirm_fn = _make_confirm_fn(data_lake)

    def _chat_and_format(message, history, sid, recipe_source, phase):
        history, text, proposals, ready = chat_fn(
            message, history, sid, recipe_source, phase,
        )
        rows = _proposals_to_rows(proposals)
        return (
            history,
            text,
            proposals,
            gr.update(value=rows),
            gr.update(interactive=ready),
        )

    def _handle_file_upload(file_obj, history, sid, phase):
        if file_obj is None:
            return history, "", [], gr.update(), gr.update(interactive=False)
        text = _extract_file_text(
            file_obj.name if hasattr(file_obj, "name") else str(file_obj),
            client=provider.client,
        )
        if not text.strip():
            history = list(history)
            history.append({
                "role":    "assistant",
                "content": "No pude extraer texto del archivo. Intenta con un PDF o Excel con texto.",
            })
            return history, "", [], gr.update(), gr.update(interactive=False)
        return _chat_and_format(
            f"[Contenido de archivo]\n{text}", history, sid, "file_content", phase,
        )

    def _confirm_and_save(table_rows, sid, current_phase, history):
        if current_phase not in _PHASE_SEQUENCE:
            yield (
                gr.update(interactive=False),
                "El inventario ya está completamente estructurado.",
                gr.update(),
                current_phase,
                gr.update(),
                gr.update(),
            )
            return

        # First yield: loading state
        yield (
            gr.update(interactive=False),   # confirm_btn
            "Guardando...",                  # status_md
            gr.update(),                     # chatbot
            current_phase,                   # phase_state (unchanged during save)
            gr.update(),                     # table
            gr.update(),                     # phase_md
        )

        current_category = _PHASE_CATEGORY[current_phase]
        status  = ""
        success = False
        for status, success in confirm_fn(table_rows, sid, current_category):
            pass

        new_history  = list(history)
        new_phase    = current_phase
        new_table    = gr.update()
        new_phase_md = gr.update()

        if success:
            phase_idx = _PHASE_SEQUENCE.index(current_phase)
            if phase_idx < len(_PHASE_SEQUENCE) - 1:
                new_phase = _PHASE_SEQUENCE[phase_idx + 1]
                greeting  = _phase_greeting(new_phase, data_lake)
                new_history.append({"role": "assistant", "content": greeting})
                # Pre-seed next phase agent memory with its greeting
                _next = create_agent(
                    StructuringAgent, provider=provider, name="structuring_agent"
                )
                _next.load_state(data_lake, session_id=_agent_session_key(sid, new_phase))
                if not _next.memory.get_messages():
                    _next.memory.add_assistant(greeting)
                    _next.save_state(data_lake, session_id=_agent_session_key(sid, new_phase))
                new_table    = gr.update(value=[])
                new_phase_md = gr.update(value=_PHASE_LABEL[new_phase])
            else:
                completion = (
                    "¡Listo! Tu inventario está completamente estructurado. "
                    "Puedes avanzar al siguiente paso: Manual Operativo."
                )
                new_history.append({"role": "assistant", "content": completion})
                new_phase    = "done"
                new_table    = gr.update(value=[])

        # Second yield: final state
        yield (
            gr.update(interactive=False),   # confirm_btn
            status,                          # status_md
            new_history,                     # chatbot
            new_phase,                       # phase_state
            new_table,                       # table
            new_phase_md,                    # phase_md
        )

    # Wiring
    send_btn.click(
        fn=_chat_and_format,
        inputs=[textbox, chatbot, session_id, recipe_source_state, phase_state],
        outputs=[chatbot, textbox, proposals_state, table, confirm_btn],
    )

    file_upload.upload(
        fn=_handle_file_upload,
        inputs=[file_upload, chatbot, session_id, phase_state],
        outputs=[chatbot, textbox, proposals_state, table, confirm_btn],
    )

    confirm_btn.click(
        fn=_confirm_and_save,
        inputs=[table, session_id, phase_state, chatbot],
        outputs=[confirm_btn, status_md, chatbot, phase_state, table, phase_md],
        show_progress="hidden",
    )
