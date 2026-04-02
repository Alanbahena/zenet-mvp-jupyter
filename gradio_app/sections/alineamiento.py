"""Alineamiento section — recipe capture and inventory proposal UI.

Guides the operator through capturing all their recipes conversationally or
via file upload. Each recipe is previewed in real time (name, category,
description, steps, ingredients, inventory proposals). The operator confirms
to persist Recipe + InventoryItem entities to DataLake.

No LangGraph — AlignmentAgent is called directly per turn. Draft accumulates
inside AlignmentAgent's _data_store across turns; gr.State holds the last
output for the right-column preview.
"""
from __future__ import annotations

import re
from typing import Any

import gradio as gr

from core.agents.alignment_agent import AlignmentAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from gradio_app.session import stable_entity_id
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES, InventoryItem, Ingredient, Recipe
from core.domain.serialization import (
    inventory_item_to_dict,
    recipe_to_dict,
    recipe_unit_conversion_to_dict,
)
from core.operations.normalization import RecipeUnitConversionEntry, RecipeUnitConversionKey

# Perecedero=1, No perecedero=2 — fixed IDs from DEFAULT_INVENTORY_CATEGORIES
_INVENTORY_CATEGORY_IDS = {"Perecedero": 1, "No perecedero": 2}


# ---------------------------------------------------------------------------
# Initial greeting
# ---------------------------------------------------------------------------

def _initial_greeting(_level: int = 1) -> list[dict]:
    """Return the opening chatbot message for the Alineamiento section."""
    content = (
        "Continuemos ahora con la sección de alineamiento de recetas. "
        "Aquí vamos a capturar todas las recetas de tu menú — nombre, ingredientes con "
        "cantidades y unidades, y pasos de preparación — para tener tu operación "
        "documentada y lista. ¿Listo para empezar?"
    )
    return [{"role": "assistant", "content": content}]


# ---------------------------------------------------------------------------
# Context loader
# ---------------------------------------------------------------------------

def _load_alignment_context(data_lake: Any, session_id: str) -> dict:
    """Load all entities needed by AlignmentAgent._generate_prompt.

    Returns dict with restaurant info, entity lists, data_lake, and session_id.
    Mirrors _load_configuration_context pattern from configuracion.py.
    """
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

    standardization_level = 1
    restaurant_description = ""
    classification_data = data_lake.load_entity("classification", entity_id)
    if classification_data:
        standardization_level = classification_data.get("standardization_level", 1)
        restaurant_description = classification_data.get("restaurant_description", "")

    categories = []
    for eid in data_lake.list_entity_ids("category_recipe"):
        e = data_lake.load_entity("category_recipe", eid)
        if e:
            categories.append(e["name"])

    families = []
    for eid in data_lake.list_entity_ids("family_inventory"):
        e = data_lake.load_entity("family_inventory", eid)
        if e:
            families.append(e["name"])

    recipe_units = []
    for eid in data_lake.list_entity_ids("recipe_unit"):
        e = data_lake.load_entity("recipe_unit", eid)
        if e:
            recipe_units.append(e["symbol"])

    inventory_units = []
    for eid in data_lake.list_entity_ids("inventory_unit"):
        e = data_lake.load_entity("inventory_unit", eid)
        if e:
            inventory_units.append(e["symbol"])

    existing_inventory_items = []
    for eid in data_lake.list_entity_ids("inventory_item"):
        e = data_lake.load_entity("inventory_item", eid)
        if e:
            existing_inventory_items.append(e["name"])

    # Build lookup maps for resolving confirmed equivalences
    ru_id_to_symbol: dict[int, str] = {}
    for eid in data_lake.list_entity_ids("recipe_unit"):
        e = data_lake.load_entity("recipe_unit", eid)
        if e:
            ru_id_to_symbol[int(eid)] = e["symbol"]

    iu_id_to_symbol: dict[int, str] = {}
    for eid in data_lake.list_entity_ids("inventory_unit"):
        e = data_lake.load_entity("inventory_unit", eid)
        if e:
            iu_id_to_symbol[int(eid)] = e["symbol"]

    item_id_to_name: dict[int, str] = {}
    for eid in data_lake.list_entity_ids("inventory_item"):
        e = data_lake.load_entity("inventory_item", eid)
        if e:
            item_id_to_name[int(eid)] = e["name"]

    confirmed_equivalences: list[str] = []
    for eid in data_lake.list_entity_ids("recipe_unit_conversion"):
        e = data_lake.load_entity("recipe_unit_conversion", eid)
        if not e:
            continue
        ru_symbol  = ru_id_to_symbol.get(e.get("recipe_unit_id", 0), "?")
        base_sym   = iu_id_to_symbol.get(e.get("base_unit_id", 0), "?")
        item_name  = item_id_to_name.get(e.get("inventory_item_id") or 0, "?")
        qty        = e.get("quantity", "?")
        confirmed_equivalences.append(
            f"1 {ru_symbol} de {item_name} ≈ {qty} {base_sym}"
        )

    return {
        "restaurant_name":           restaurant_name,
        "restaurant_type":           restaurant_type,
        "restaurant_description":    restaurant_description,
        "standardization_level":     standardization_level,
        "categories":                categories,
        "families":                  families,
        "recipe_units":              recipe_units,
        "inventory_units":           inventory_units,
        "existing_inventory_items":  existing_inventory_items,
        "confirmed_equivalences":    confirmed_equivalences,
        "data_lake":                 data_lake,
        "session_id":                session_id,
    }


# ---------------------------------------------------------------------------
# File text extraction
# ---------------------------------------------------------------------------

def _extract_text_via_vision(image_bytes: bytes, media_type: str, client: Any) -> str:
    """Send a single image to Claude vision and return extracted text."""
    import base64
    image_data = base64.standard_b64encode(image_bytes).decode("utf-8")
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "Extract all text from this image exactly as written. "
                        "If this is a recipe, preserve ingredient names, quantities, "
                        "units, and preparation steps."
                    ),
                },
            ],
        }],
    )
    return response.content[0].text if response.content else ""


def _extract_file_text(file_path: str, client: Any = None) -> str:
    """Extract plain text from PDF, Excel, or image files.

    For text-based PDFs and Excel files no API call is made.
    For image files (JPG, PNG) and image-based PDFs the content is sent to
    Claude vision to extract text. client must be an anthropic.Anthropic instance
    when vision extraction may be needed.
    """
    lower = file_path.lower()

    # --- Image files ---
    if lower.endswith((".jpg", ".jpeg")):
        with open(file_path, "rb") as f:
            return _extract_text_via_vision(f.read(), "image/jpeg", client)
    if lower.endswith(".png"):
        with open(file_path, "rb") as f:
            return _extract_text_via_vision(f.read(), "image/png", client)
    if lower.endswith(".webp"):
        with open(file_path, "rb") as f:
            return _extract_text_via_vision(f.read(), "image/webp", client)

    # --- PDF: try text extraction first, fall back to vision ---
    if lower.endswith(".pdf"):
        import pypdf
        reader = pypdf.PdfReader(file_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text
        # Image-based PDF — render each page and send to Claude vision
        import fitz  # pymupdf
        doc = fitz.open(file_path)
        pages_text: list[str] = []
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            page_text = _extract_text_via_vision(pix.tobytes("png"), "image/png", client)
            if page_text.strip():
                pages_text.append(page_text)
        return "\n".join(pages_text)

    # --- Excel ---
    if lower.endswith((".xlsx", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        lines = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                line = "  ".join(str(c) for c in row if c is not None)
                if line.strip():
                    lines.append(line)
        return "\n".join(lines)

    return ""


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

_LINK_STATUS_ES = {
    "matched_existing": "existente",
    "new":              "nuevo",
    "needs_resolution": "por resolver",
}

_PROPOSAL_STATUS_ES = {
    "new":              "nuevo",
    "matched_existing": "existente",
}


def _ingredients_to_rows(ingredients: list[dict]) -> list[list]:
    return [
        [
            ing.get("name", ""),
            ing.get("quantity", ""),
            ing.get("unit_symbol", ""),
            ing.get("equivalent") or "",
            ing.get("matched_item_name") or _LINK_STATUS_ES.get(
                ing.get("inventory_link_status", ""), ing.get("inventory_link_status", "")
            ),
        ]
        for ing in ingredients
    ]


def _proposals_to_rows(proposals: list[dict]) -> list[list]:
    return [
        [
            p.get("name", ""),
            p.get("category", ""),
            p.get("family") or "",
            _PROPOSAL_STATUS_ES.get(p.get("status", ""), p.get("status", "")),
        ]
        for p in proposals
    ]


# ---------------------------------------------------------------------------
# Agent state reset
# ---------------------------------------------------------------------------

def _reset_agent_draft(data_lake: Any, session_id: str, provider: Any) -> None:
    """Clear AlignmentAgent draft and memory after a recipe is confirmed.

    Loads the agent state, clears recipe_draft, inventory_proposals, and
    conversation memory, then saves back so the next recipe starts fresh.
    """
    agent = create_agent(AlignmentAgent, provider=provider, name="alignment_agent")
    agent.load_state(data_lake, session_id=f"alignment_agent_{session_id}")
    agent.store("recipe_draft", {})
    agent.store("inventory_proposals", [])
    agent.memory.clear()
    agent.save_state(data_lake, session_id=f"alignment_agent_{session_id}")


# ---------------------------------------------------------------------------
# Chat handler
# ---------------------------------------------------------------------------

def _make_chat_fn(provider: Any, data_lake: Any, initial_greeting_text: str):
    def chat_fn(
        message: str,
        history: list,
        session_id: str,
        recipe_source: str,
        current_page_index: int,
    ):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, "", {}, [], False, False, None

        if not (message or "").strip():
            return history, "", {}, [], False, False, None

        agent = create_agent(AlignmentAgent, provider=provider, name="alignment_agent")
        agent.load_state(data_lake, session_id=f"alignment_agent_{session_id}")

        # On the first turn inject the greeting into memory so the agent has context
        if not agent.memory.get_messages():
            agent.memory.add_assistant(initial_greeting_text)

        ctx = _load_alignment_context(data_lake, session_id)

        try:
            result = agent.run(
                input_data={
                    "user_message":  message,
                    "recipe_source": recipe_source,
                    "page_index":    current_page_index,
                },
                context=ctx,
            )
            reply               = result["reply"]
            recipe_draft        = result["recipe_draft"]
            inventory_proposals = result["inventory_proposals"]
            recipe_count        = result.get("recipe_count")
            recipe_ready        = bool(result.get("ready_to_save", False))
            show_file_upload    = bool(result.get("show_file_upload", False))
        except Exception:
            reply               = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
            recipe_draft        = {}
            inventory_proposals = []
            recipe_count        = None
            recipe_ready        = False
            show_file_upload    = False

        agent.save_state(data_lake, session_id=f"alignment_agent_{session_id}")

        history = list(history)
        history.append({"role": "user",      "content": message})
        history.append({"role": "assistant", "content": reply})

        return history, "", recipe_draft, inventory_proposals, show_file_upload, recipe_ready, recipe_count

    return chat_fn


# ---------------------------------------------------------------------------
# Confirm handler
# ---------------------------------------------------------------------------

def _make_confirm_fn(data_lake: Any):
    def confirm_fn(
        recipe_draft: dict,
        inventory_proposals: list,
        session_id: str,
    ):
        if not session_id or not recipe_draft.get("recipe_name"):
            yield "No hay receta para guardar.", False
            return

        yield "Guardando receta...", False

        try:
            # --- Resolve category_id for Recipe ---
            category_id = 1  # fallback: Perecedero
            cat_name = recipe_draft.get("recipe_category", "")
            for eid in data_lake.list_entity_ids("category_recipe"):
                e = data_lake.load_entity("category_recipe", eid)
                if e and e.get("name") == cat_name:
                    category_id = int(eid)
                    break

            # --- Next recipe ID ---
            existing_recipe_ids = [int(i) for i in data_lake.list_entity_ids("recipe")]
            recipe_id = max(existing_recipe_ids, default=0) + 1

            # --- Build lookup maps ---
            existing_item_ids = [int(i) for i in data_lake.list_entity_ids("inventory_item")]
            next_item_id = max(existing_item_ids, default=0) + 1

            ru_symbol_to_id: dict[str, int] = {}
            for eid in data_lake.list_entity_ids("recipe_unit"):
                e = data_lake.load_entity("recipe_unit", eid)
                if e:
                    ru_symbol_to_id[e["symbol"]] = int(eid)

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

            # --- Save new inventory proposals ---
            # Resolve default stock/purchase unit: prefer g, then kg, then pza, then first available.
            default_unit_id = (
                iu_symbol_to_id.get("g")
                or iu_symbol_to_id.get("kg")
                or iu_symbol_to_id.get("pza")
                or next(iter(iu_symbol_to_id.values()), None)
            )
            if default_unit_id is None:
                yield (
                    "Error: no hay unidades de inventario configuradas. "
                    "Completa la sección de Configuración antes de guardar recetas."
                ), False
                return

            proposal_name_to_id: dict[str, int] = {}
            for proposal in (inventory_proposals or []):
                name = proposal.get("name", "")
                if not name:
                    continue
                if proposal.get("status") == "new" and name not in existing_item_name_to_id:
                    cat_str = proposal.get("category", "Perecedero")
                    cat_id  = _INVENTORY_CATEGORY_IDS.get(cat_str, 1)
                    fam_name = proposal.get("family")
                    fam_id  = family_name_to_id.get(fam_name) if fam_name else None
                    unit_id = default_unit_id
                    item = InventoryItem(
                        id=next_item_id,
                        name=name,
                        stock_unit_id=unit_id,
                        purchase_unit_id=unit_id,
                        category_id=cat_id,
                        purchase_to_stock_factor=1.0,
                        family_id=fam_id,
                    )
                    data_lake.save_entity(
                        "inventory_item", next_item_id, inventory_item_to_dict(item)
                    )
                    proposal_name_to_id[name] = next_item_id
                    next_item_id += 1
                elif name in existing_item_name_to_id:
                    proposal_name_to_id[name] = existing_item_name_to_id[name]

            # --- Build ingredients + collect RecipeUnitConversion saves ---
            ingredients: list[Ingredient] = []
            ruc_saves: list[tuple] = []

            for ing_dict in (recipe_draft.get("ingredients") or []):
                ing_name    = ing_dict.get("name", "")
                ing_qty     = float(ing_dict.get("quantity") or 1)
                unit_symbol = ing_dict.get("unit_symbol", "g")
                unit_id     = ru_symbol_to_id.get(unit_symbol, 1)
                inv_item_id = proposal_name_to_id.get(ing_name)

                ingredients.append(Ingredient(
                    name=ing_name,
                    quantity=ing_qty,
                    unit_id=unit_id,
                    inventory_item_id=inv_item_id,
                ))

                equivalent = ing_dict.get("equivalent")
                if equivalent and inv_item_id:
                    match = re.search(r"[≈~]?\s*([\d.]+)\s*([a-zA-Z]+)", equivalent)
                    if match:
                        eq_qty    = float(match.group(1))
                        eq_symbol = match.group(2)
                        base_uid  = iu_symbol_to_id.get(eq_symbol)
                        ru_id     = ru_symbol_to_id.get(unit_symbol)
                        if base_uid and ru_id:
                            key   = RecipeUnitConversionKey(
                                recipe_unit_id=ru_id,
                                family_id=None,
                                inventory_item_id=inv_item_id,
                            )
                            entry = RecipeUnitConversionEntry(
                                quantity=eq_qty,
                                base_unit_id=base_uid,
                                source="agent_confirmed",
                            )
                            ruc_saves.append((key, entry))

            # --- Save Recipe ---
            recipe = Recipe(
                id=recipe_id,
                name=recipe_draft.get("recipe_name", ""),
                category_id=category_id,
                description=recipe_draft.get("recipe_description"),
                steps=recipe_draft.get("recipe_steps"),
                ingredients=ingredients,
            )
            data_lake.save_entity("recipe", recipe_id, recipe_to_dict(recipe))

            # --- Save RecipeUnitConversions ---
            for key, entry in ruc_saves:
                composite_id = f"{key.recipe_unit_id}_{key.family_id}_{key.inventory_item_id}"
                data_lake.save_entity(
                    "recipe_unit_conversion", composite_id,
                    recipe_unit_conversion_to_dict(entry, key),
                )

            saved_name = recipe_draft.get("recipe_name", "Receta")
            yield f"**{saved_name}** guardada correctamente.", True

        except Exception as exc:
            yield f"Error al guardar: {exc}", False

    return confirm_fn


# ---------------------------------------------------------------------------
# Section entry point
# ---------------------------------------------------------------------------

def render(session_id: gr.State, data_lake: Any) -> None:
    provider = ClaudeProvider()

    # --- State ---
    recipe_draft_state        = gr.State({})
    inventory_proposals_state = gr.State([])
    recipe_source_state       = gr.State("conversation")
    current_page_index_state  = gr.State(0)
    recipe_count_state        = gr.State(None)
    saved_recipes_state       = gr.State([])
    recipe_ready_state        = gr.State(False)

    # --- Greeting ---
    greeting_messages = _initial_greeting(1)
    greeting_text     = greeting_messages[0]["content"]

    # --- Layout ---
    with gr.Row():
        # LEFT — chat
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de alineamiento")
            chatbot = gr.Chatbot(label="Asistente Zenet", height="60vh", value=greeting_messages)
            textbox = gr.Textbox(
                placeholder="Escribe tu mensaje...",
                show_label=False,
                lines=3,
                max_lines=3,
            )
            send_btn = gr.Button("Enviar")
            # Revealed only after operator confirms they have a file
            # Image support deferred to post-MVP (requires Claude vision API extension)
            file_upload = gr.File(
                label="Subir archivo de recetas",
                file_types=[".pdf", ".xlsx", ".xls", ".jpg", ".jpeg", ".png", ".webp"],
            )

        # RIGHT — recipe preview
        with gr.Column(scale=1):
            progress_md     = gr.Markdown("Receta 1 de ?")
            recipe_name_md  = gr.Markdown("")
            ingredients_tbl = gr.Dataframe(
                headers=["Ingrediente", "Cantidad", "Unidad", "Equivalente", "Inventario"],
                interactive=False,
                label="Ingredientes",
            )
            proposals_tbl = gr.Dataframe(
                headers=["Artículo", "Categoría", "Familia", "Estado"],
                interactive=False,
                label="Artículos de inventario a crear",
            )
            confirm_btn = gr.Button(
                "Guardar Receta + Artículos de Inventario",
                interactive=False,
            )
            status_md = gr.Markdown("")
            saved_md  = gr.Markdown("")

    # --- Handlers ---
    chat_fn    = _make_chat_fn(provider, data_lake, greeting_text)
    confirm_fn = _make_confirm_fn(data_lake)

    def _chat_and_format(
        message, history, sid,
        recipe_source, page_index, recipe_count,
    ):
        history, text, draft, proposals, _show_file, ready, new_count = chat_fn(
            message, history, sid, recipe_source, page_index,
        )
        resolved_count = new_count if new_count is not None else recipe_count
        total = str(resolved_count) if resolved_count is not None else "?"
        progress = f"Receta {page_index + 1} de {total}"
        ingredients = draft.get("ingredients") or []
        ing_rows  = _ingredients_to_rows(ingredients)
        prop_rows = _proposals_to_rows(proposals)
        name_md   = f"### {draft.get('recipe_name', '')}" if draft.get("recipe_name") else ""
        ing_label = f"Ingredientes ({len(ingredients)})" if ingredients else "Ingredientes"
        return (
            history,
            text,
            draft,
            proposals,
            ready,
            resolved_count,
            gr.update(interactive=ready),
            name_md,
            gr.update(value=ing_rows, label=ing_label),
            prop_rows,
            progress,
        )

    def _handle_file_upload(file_obj, history, sid, page_index, recipe_count):
        """Extract text from uploaded file and run one agent turn."""
        if file_obj is None:
            return history, "", {}, [], False, None, gr.update(interactive=False), "", [], [], gr.update()
        text = _extract_file_text(
            file_obj.name if hasattr(file_obj, "name") else str(file_obj),
            client=provider.client,
        )
        if not text.strip():
            history = list(history)
            history.append({
                "role": "assistant",
                "content": "No pude extraer texto del archivo. Intenta con un PDF o Excel con texto.",
            })
            return history, "", {}, [], False, None, gr.update(interactive=False), "", [], [], gr.update()
        # Inject file content as user turn
        return _chat_and_format(
            f"[Contenido de archivo]\n{text}", history, sid, "file_content", page_index, recipe_count,
        )

    def _confirm_and_save(
        draft, proposals, sid,
        saved_recipes, page_index, history, recipe_count,
    ):
        # First yield: loading state
        yield (
            gr.update(),                   # recipe_draft_state — no change yet
            gr.update(interactive=False),  # confirm_btn
            "Guardando...",                # status_md
            gr.update(),                   # saved_md
            gr.update(),                   # saved_recipes_state
            gr.update(),                   # current_page_index_state
            gr.update(),                   # inventory_proposals_state
            gr.update(),                   # chatbot — no change yet
            gr.update(),                   # progress_md — no change yet
        )

        status  = ""
        success = False
        for status, success in confirm_fn(draft, proposals, sid):
            pass

        saved = list(saved_recipes)
        new_history = list(history)
        if success:
            recipe_name = draft.get("recipe_name", "Receta")
            saved.append(f"{recipe_name} ✓")
            _reset_agent_draft(data_lake, sid, provider)
            new_index = page_index + 1
            new_draft = {}
            new_proposals = []

            all_done = recipe_count is not None and new_index >= recipe_count
            if all_done:
                next_prompt = (
                    f"¡Listo! **{recipe_name}** guardada correctamente. "
                    f"Has completado las {recipe_count} recetas de tu menú. "
                    "Ya tienes toda la información capturada para continuar. "
                    "Cuando estés listo, puedes avanzar al paso 5: **Estructura**, "
                    "donde vamos a completar los artículos de inventario con sus unidades y equivalencias."
                )
            else:
                next_prompt = (
                    f"¡Listo! **{recipe_name}** guardada correctamente. "
                    "¿Tienes otra receta que capturar? Si es así, dime cómo la quieres compartir "
                    "— me la dicas aquí o tienes un archivo (PDF, imagen o Excel). "
                    "Si ya terminaste con todas tus recetas, podemos avanzar al paso 5: Estructura."
                )
            new_history.append({"role": "assistant", "content": next_prompt})

            # Inject into agent memory so next turn has context
            _agent = create_agent(AlignmentAgent, provider=provider, name="alignment_agent")
            _agent.load_state(data_lake, session_id=f"alignment_agent_{sid}")
            _agent.memory.add_assistant(next_prompt)
            _agent.save_state(data_lake, session_id=f"alignment_agent_{sid}")
        else:
            new_index     = page_index
            new_draft     = draft
            new_proposals = proposals

        saved_list_md = "\n".join(f"- {r}" for r in saved) if saved else ""
        total = str(recipe_count) if recipe_count is not None else "?"
        new_progress = f"Receta {new_index + 1} de {total}"

        # Second yield: final state
        yield (
            new_draft,
            gr.update(interactive=False),
            status,
            saved_list_md,
            saved,
            new_index,
            new_proposals,
            new_history,
            new_progress,
        )

    # --- Wiring ---
    send_btn.click(
        fn=_chat_and_format,
        inputs=[
            textbox, chatbot, session_id,
            recipe_source_state, current_page_index_state, recipe_count_state,
        ],
        outputs=[
            chatbot, textbox,
            recipe_draft_state, inventory_proposals_state,
            recipe_ready_state, recipe_count_state,
            confirm_btn, recipe_name_md, ingredients_tbl, proposals_tbl,
            progress_md,
        ],
    )

    file_upload.upload(
        fn=_handle_file_upload,
        inputs=[file_upload, chatbot, session_id, current_page_index_state, recipe_count_state],
        outputs=[
            chatbot, textbox,
            recipe_draft_state, inventory_proposals_state,
            recipe_ready_state, recipe_count_state,
            confirm_btn, recipe_name_md, ingredients_tbl, proposals_tbl,
            progress_md,
        ],
    )

    confirm_btn.click(
        fn=_confirm_and_save,
        inputs=[
            recipe_draft_state, inventory_proposals_state, session_id,
            saved_recipes_state, current_page_index_state, chatbot, recipe_count_state,
        ],
        outputs=[
            recipe_draft_state, confirm_btn, status_md, saved_md,
            saved_recipes_state, current_page_index_state, inventory_proposals_state,
            chatbot, progress_md,
        ],
        show_progress="hidden",
    )
