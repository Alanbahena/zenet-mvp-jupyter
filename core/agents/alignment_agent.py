"""
AlignmentAgent -- recipe extraction and inventory proposal agent for the Alineamiento section.

Extracts recipes from operator conversation or uploaded file content, proposes inventory
item shells from ingredients, handles deduplication against existing inventory, and
supports entity creation with operator confirmation.

No-hallucination rule: only extract data present in the file or operator's words.
Draft accumulates across turns via _data_store; nothing is persisted to DataLake until
the operator confirms via the UI Confirm button.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
from core.domain.data_model import STANDARD_RECIPE_UNIT_SYMBOLS


_SYSTEM_PROMPT = """Eres Zeni, el asistente de alineamiento de Zenet.

Tu objetivo es extraer las recetas del operador y proponer los artículos de inventario \
que se necesitan a partir de los ingredientes.

## Inicio de sesión (OBLIGATORIO — sigue este flujo exactamente)

El flujo de inicio tiene tres pasos en orden estricto. No los saltes, no los combines.

**Paso 1 — Cuando el operador confirme que está listo** (diga "listo", "sí", "dale", etc.):
Responde ÚNICAMENTE con la pregunta: "¿Cuántas recetas tienes aproximadamente?"
No digas nada más. No menciones archivos. No empieces a capturar recetas.
Todos los campos JSON excepto `reply` deben ser null en esta respuesta.

**Paso 2 — Cuando el operador responda la cantidad** (o diga que no sabe):
Haz la segunda pregunta según el nivel de estandarización del contexto:
- Nivel 1: "¿Las tienes en un archivo (PDF, imagen o Excel) o las capturamos juntos aquí \
en el chat?"
- Nivel 2: "Puedes subirlas en formato PDF, imagen o Excel cuando quieras — o si prefieres, \
las capturamos juntos aquí en el chat. ¿Cómo lo hacemos?"
Todos los campos JSON excepto `reply` deben ser null en esta respuesta.

**Paso 3 — Cuando el operador responda el formato:**
Comienza con la primera receta.

**Excepción:** Si el operador empieza a dictar una receta sin pasar por el flujo de inicio, \
adáptate y captúrala directamente sin interrumpir.

## Reglas de extracción

**Sin alucinaciones:** Solo extrae información presente en las palabras del operador o \
en el archivo cargado. No inventes, no asumas, no infieras ingredientes que no se \
hayan mencionado. Si la fuente es escasa, el borrador debe ser corto y fiel.

**Pasos de preparación:** Si no encuentras los pasos de preparación en la fuente, \
pregunta una sola vez al operador. Si el operador no los proporciona o dice que no los \
tiene, guarda `recipe_steps` como null. No repitas la pregunta.

**Equivalentes por ingrediente:** Para unidades de receta no estándar (taza, cda, cdta, \
oz, manojo, pizca, etc.), primero pregunta al operador si conoce el equivalente en gramos \
o mililitros. Ejemplo: "¿Sabes cuántos gramos equivale aproximadamente 1 taza de harina \
en tu receta?". Solo si el operador dice que no sabe o no tiene el dato, propón tú el \
equivalente usando conocimiento culinario (e.g. 1 taza de harina ≈ 120 g) y pídele que \
confirme o corrija. Nunca propongas un equivalente sin antes preguntarle al operador. \
Nunca apliques una conversión universal de volumen a masa — siempre es por ingrediente \
específico.

**Unidades estándar:** Solo g, kg, ml, L, pza son unidades estándar y no requieren \
equivalente. Cualquier otra unidad requiere un valor en el campo `equivalent`.

**Fallback de unidad de inventario:** Si la unidad de receta no tiene equivalente \
directo en inventario: sólidos → g o kg, líquidos → ml o L, contables → pza.

**Categoría de inventario:** El campo `category` en cada artículo de inventario propuesto \
debe ser exactamente "Perecedero" o "No perecedero". No uses otros valores.

**Familia de inventario:** El campo `family` debe ser elegido de la lista de familias \
disponibles en el contexto. Si ninguna aplica, usa null.

**Creación de entidades:** Si la receta usa una categoría, familia, o unidad de receta \
que no está en el contexto, primero propón mapear a una existente. Solo llama la \
herramienta `create_entity` si el operador confirma explícitamente que quiere crear \
una nueva entidad. Nunca crees entidades sin confirmación del operador.

## Reglas de comunicación

- Siempre en español
- Tono cercano y directo, sin tecnicismos
- Máximo 3–4 oraciones de respuesta conversacional en el campo `reply`
- Haz una pregunta a la vez — no acumules preguntas
- Si extraes múltiples ingredientes, confirma el borrador completo antes de avanzar

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos campos:
- "reply": tu respuesta conversacional (nunca JSON dentro de este campo)
- "recipe_name": nombre de la receta, o null si aún no se tiene
- "recipe_category": categoría de la receta (de la lista disponible en contexto), o null
- "recipe_description": descripción breve de la receta, o null
- "recipe_steps": lista de pasos de preparación como strings, o null
- "ingredients": lista de objetos con exactamente estos campos:
    - "name": nombre del ingrediente (string)
    - "quantity": cantidad numérica (float)
    - "unit_symbol": símbolo de la unidad de receta, e.g. "g", "kg", "taza" (string)
    - "equivalent": equivalente en masa/volumen para unidades no estándar, e.g. "≈ 120 g" \
(string o null)
    - "inventory_link_status": "matched_existing" si ya existe en inventario, "new" si es \
nuevo, "needs_resolution" si no se puede determinar (string)
    - "matched_item_name": nombre canónico del artículo si inventory_link_status es \
"matched_existing", null en otro caso (string o null)
- "inventory_proposals": lista de objetos con exactamente estos campos:
    - "name": nombre canónico del artículo de inventario (string)
    - "category": exactamente "Perecedero" o "No perecedero" (string)
    - "family": nombre de familia del contexto, o null si ninguna aplica (string o null)
    - "status": "new" si es un artículo nuevo, "matched_existing" si ya existe (string)
- "recipe_count": número total de recetas que el operador mencionó tener (entero), o null \
si no lo ha mencionado aún. Solo actualiza este campo cuando el operador proporcione el número \
por primera vez — no lo repitas en cada turno.
- "show_file_upload": true si el operador indica que va a proporcionar recetas en un archivo; \
false en cualquier otro caso
"""


class _IngredientProposal(BaseModel):
    name: str
    quantity: float
    unit_symbol: str
    equivalent: str | None = None
    inventory_link_status: str             # "matched_existing" | "new" | "needs_resolution"
    matched_item_name: str | None = None   # canonical name if matched_existing


class _InventoryProposal(BaseModel):
    name: str                              # canonical inventory item name
    category: str                          # "Perecedero" | "No perecedero"
    family: str | None = None             # FamilyInventory name from context; null if none fits
    status: str                           # "new" | "matched_existing"


class _AlignmentResponse(BaseModel):
    reply: str
    recipe_name: str | None = None
    recipe_category: str | None = None
    recipe_description: str | None = None
    recipe_steps: list[str] | None = None
    ingredients: list[_IngredientProposal] | None = None
    inventory_proposals: list[_InventoryProposal] | None = None
    recipe_count: int | None = None
    show_file_upload: bool = False


class AlignmentAgent(BaseAgent):
    """
    Conversational recipe extraction and inventory proposal agent for the Alineamiento section.

    Extracts recipes from operator messages or uploaded file content, proposes inventory
    item shells from ingredients, handles deduplication against existing inventory, and
    supports entity creation with operator confirmation.

    No-hallucination rule: only extract data present in the file or operator's words.
    Draft accumulates across turns; nothing is persisted to DataLake until the operator
    confirms via the UI Confirm button.

    Input:
        user_message:  Message from operator or extracted file content.
        recipe_source: 'file_content' or 'conversation'
        page_index:    Which recipe in a multi-recipe file (0-based). 0 for single.

    Output:
        reply:               Conversational response in Spanish.
        recipe_draft:        Dict with recipe fields for UI preview.
        inventory_proposals: List of dicts for inventory panel.
        raw_response:        Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "Message from operator or extracted file content.",
        "recipe_source": "'file_content' or 'conversation'",
        "page_index": "Which recipe in a multi-recipe file (0-based). 0 for single.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply": "Conversational response in Spanish.",
        "recipe_draft": "Dict with recipe fields for UI preview.",
        "inventory_proposals": "List of dicts for inventory panel.",
        "raw_response": "Full LLM response string.",
        "show_file_upload": "True when operator indicates they will provide recipes via file.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _AlignmentResponse

    def __post_init__(self) -> None:
        super().__post_init__()
        self.register_tool(
            name="create_entity",
            func=self._create_entity_tool,
            description=(
                "Create a new category_recipe, family_inventory, or recipe_unit. "
                "Only call after the operator has explicitly confirmed they want to create it."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["category_recipe", "family_inventory", "recipe_unit"],
                        "description": "Type of entity to create.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name for the new entity.",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol (required only for recipe_unit, e.g. 'manojo').",
                    },
                },
                "required": ["entity_type", "name"],
            },
        )

    def _create_entity_tool(
        self,
        entity_type: str,
        name: str,
        symbol: str | None = None,
    ) -> str:
        """Create a new category_recipe, family_inventory, or recipe_unit.

        Only called after explicit operator confirmation. Saves to DataLake, assigns
        next sequential ID, updates in-memory context lists, and returns a confirmation
        string for the LLM to continue.
        """
        if entity_type not in {"category_recipe", "family_inventory", "recipe_unit"}:
            return f"Error: unknown entity_type '{entity_type}'."

        data_lake = getattr(self, "_data_lake", None)
        if data_lake is None:
            return "Error: data_lake not available — tool called before context was set."

        existing_ids = data_lake.list_entity_ids(entity_type)
        next_id = max((int(eid) for eid in existing_ids), default=0) + 1

        if entity_type == "category_recipe":
            data_lake.save_entity(entity_type, next_id, {"id": next_id, "name": name})
            ctx = getattr(self, "_context", {})
            if "categories" in ctx:
                ctx["categories"].append(name)
            return f"Categoría '{name}' creada con id {next_id}."

        elif entity_type == "family_inventory":
            data_lake.save_entity(entity_type, next_id, {"id": next_id, "name": name})
            ctx = getattr(self, "_context", {})
            if "families" in ctx:
                ctx["families"].append(name)
            return f"Familia '{name}' creada con id {next_id}."

        elif entity_type == "recipe_unit":
            if not symbol:
                return "Error: symbol es requerido para recipe_unit."
            data_lake.save_entity(
                entity_type, next_id, {"id": next_id, "name": name, "symbol": symbol}
            )
            ctx = getattr(self, "_context", {})
            if "recipe_units" in ctx:
                ctx["recipe_units"].append(symbol)
            is_nonstandard = symbol not in STANDARD_RECIPE_UNIT_SYMBOLS
            confirmation = f"Unidad '{name}' ({symbol}) creada con id {next_id}."
            if is_nonstandard:
                confirmation += (
                    f" Como '{symbol}' no es una unidad estándar, "
                    "pregunta al operador cuántos gramos o ml equivale aproximadamente 1 unidad."
                )
            return confirmation

        return "Error: entity_type no reconocido."

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        # Store references for create_entity tool access during tool calling loop
        self._data_lake = context.get("data_lake")
        self._session_id = context.get("session_id", "")
        self._context = context  # tool appends to categories/families/recipe_units lists

        system = _SYSTEM_PROMPT

        # Inject restaurant + pipeline context
        context_parts: list[str] = []
        if context.get("restaurant_name"):
            context_parts.append(f"Restaurante: {context['restaurant_name']}")
        if context.get("restaurant_type"):
            context_parts.append(f"Tipo: {context['restaurant_type']}")
        if context.get("restaurant_description"):
            context_parts.append(f"Descripción: {context['restaurant_description']}")
        if context.get("standardization_level"):
            context_parts.append(f"Nivel de estandarización: {context['standardization_level']}")
        if context.get("categories"):
            context_parts.append(
                f"Categorías de receta disponibles: {', '.join(context['categories'])}"
            )
        if context.get("families"):
            context_parts.append(
                f"Familias de inventario disponibles: {', '.join(context['families'])}"
            )
        if context.get("existing_inventory_items"):
            context_parts.append(
                f"Artículos de inventario existentes: {', '.join(context['existing_inventory_items'])}"
            )
        if context.get("recipe_units"):
            context_parts.append(
                f"Unidades de receta disponibles: {', '.join(context['recipe_units'])}"
            )
        if context.get("inventory_units"):
            context_parts.append(
                f"Unidades de inventario disponibles: {', '.join(context['inventory_units'])}"
            )
        if context.get("confirmed_equivalences"):
            context_parts.append(
                "Equivalentes ya confirmados (no preguntes de nuevo por estos):\n"
                + "\n".join(f"  - {eq}" for eq in context["confirmed_equivalences"])
            )

        if context_parts:
            system = system + "\n\n## Contexto del restaurante\n" + "\n".join(context_parts)

        # Inject accumulated draft so agent knows what was already captured
        draft = self.retrieve("recipe_draft", {})
        if draft:
            system = (
                system
                + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
                + json.dumps(draft, ensure_ascii=False, indent=2)
            )

        # Build user message — add source framing for file content
        page_index = input_data.get("page_index", 0)
        recipe_source = input_data.get("recipe_source", "conversation")
        user_msg = input_data["user_message"]
        if recipe_source == "file_content":
            user_msg = f"[Contenido de archivo, receta #{page_index + 1}]\n{user_msg}"

        return system, user_msg

    def _process_response(self, response: str) -> dict[str, Any]:
        # _parse_response() returns dict[str, Any] — already model_dump'd by BaseAgent
        data = self._parse_response(response)

        # Merge non-None scalar fields into existing draft
        existing_draft: dict[str, Any] = self.retrieve("recipe_draft", {})
        new_fields: dict[str, Any] = {}
        for field_name in (
            "recipe_name",
            "recipe_category",
            "recipe_description",
            "recipe_steps",
        ):
            val = data.get(field_name)
            if val is not None:
                new_fields[field_name] = val

        # Ingredients: overwrite if present (list[dict] — already dumped)
        ingredients = data.get("ingredients")
        if ingredients is not None:
            new_fields["ingredients"] = ingredients

        merged_draft = {**existing_draft, **new_fields}
        self.store("recipe_draft", merged_draft)

        # Inventory proposals: overwrite if present (list[dict] — already dumped)
        proposals = list(data.get("inventory_proposals") or [])
        self.store("inventory_proposals", proposals)

        # recipe_count: persist once set, never overwrite with null
        recipe_count = data.get("recipe_count")
        if recipe_count is not None:
            self.store("recipe_count", recipe_count)
        else:
            recipe_count = self.retrieve("recipe_count", None)

        return {
            "reply": data.get("reply", ""),
            "recipe_draft": merged_draft,
            "inventory_proposals": proposals,
            "raw_response": response,
            "recipe_count": recipe_count,
            "show_file_upload": bool(data.get("show_file_upload", False)),
        }
