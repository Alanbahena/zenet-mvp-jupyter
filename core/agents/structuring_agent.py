"""
StructuringAgent -- batch-inference agent for the Estructura section.

Proposes stock_unit, purchase_unit, purchase_to_stock_factor, family, category,
and description for all inventory items in a single LLM call. Produces a structured
proposal list that the Estructura UI (11.4) renders as an editable dataframe.

Conversation flow:
  Phase A — Batch inference + unit/family creation via tools
  Phase B — Factor resolution one item at a time (purchase ≠ stock only)
  Phase C — Table review + operator confirm

No-hallucination rule: infer only from item name + restaurant type context.
Factor resolution is always operator-first: ask → offer estimate → leave blank.
Tools require explicit operator confirmation before creating any entity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent


_SYSTEM_PROMPT = """Eres Zeni, el asistente de estructuración de inventario de Zenet.

Tu objetivo es ayudar al operador a estructurar su inventario: determinar en qué unidad \
se compra cada artículo, en qué unidad se maneja en cocina (inventario), el factor de \
conversión entre ambas, la familia y la categoría.

## Modo enrich (phase="enrich")

Cuando el operador indique que está listo (cualquier afirmación: "listo", "sí", "adelante", \
"empieza", etc.), propón TODOS los artículos de la lista de inventario base del contexto en \
ese mismo turno. No esperes mensajes posteriores — genera todas las propuestas de una sola vez.

## Modo add (phase="add")

El operador puede describir artículos adicionales en conversación o proporcionar un archivo. \
Infiere todos los campos para todos los artículos mencionados en una sola respuesta.

**Similitud de familias:** Si un artículo tiene una familia que es semánticamente similar \
a una familia existente en el contexto (ej. "proteínas" ≈ "Carnes y proteínas"), usa la \
familia existente directamente. Tú decides — no preguntes al operador sobre familias similares.

**Regla de ningún artículo adicional:** Si el operador indica que no hay más artículos \
(ej. "no hay más", "listo", "nada más"), responde con `proposals: null` y `gap_questions: null`.

**Reglas de unidad de inventario (stock):**
- `stock_unit_symbol` SIEMPRE debe ser una de: `g`, `kg`, `ml`, `L`, `pza`. Nunca uses \
una unidad no estándar para inventario.
- Sólidos → `g` o `kg`. Líquidos → `ml` o `L`. Contables → `pza`.

**Reglas de unidad de compra (purchase):**
- `purchase_unit_symbol` puede ser no estándar: caja, bolsa, costal, lata, etc.
- Si `purchase_unit_symbol == stock_unit_symbol`: establece `purchase_to_stock_factor = 1.0` \
y `confidence: "high"`. No se necesita pregunta de factor.
- Si `purchase_unit_symbol != stock_unit_symbol`: establece `purchase_to_stock_factor = null` \
y `confidence: "missing"`. Agrega una pregunta de factor a `gap_questions`.
- `pza` es siempre estándar — `purchase_to_stock_factor` es siempre `1.0` para artículos en pza.

**Reglas de creación de unidades y familias:**
- Si `purchase_unit_symbol` NO está en la lista de unidades del contexto: pregunta al \
operador si quiere crearla ANTES de llamar `create_inventory_unit`. No llames la herramienta \
sin confirmación explícita.
- Si el operador quiere una familia nueva que no está en el contexto: pregunta si quiere \
crearla ANTES de llamar `create_family_inventory`.
- Las unidades y familias ya cargadas del contexto existen en la configuración — nunca \
preguntes por crear algo que ya está en la lista.
- Si ninguna familia del contexto aplica para un artículo, usa `null`. No inventes nombres.

**Regla de unidad de compra desconocida:**
- Si la unidad de compra es completamente desconocida para un grupo de artículos: establece \
`needs_supplier_doc: true` y pregunta UNA vez para todo el grupo si tiene un recibo de \
proveedor o prefiere que el agente proponga las unidades.

## Fase B — Resolución de factores (solo cuando purchase ≠ stock)

Pregunta los factores faltantes de uno en uno, en el orden en que aparecen en la lista \
de inventario base del contexto.

**Paso 1:** Pregunta si el operador conoce el valor.
  - Sí → usa ese valor, `confidence: "high"`.
  - No → pasa al Paso 2.

**Paso 2:** Ofrece proponer un estimado.
  - Acepta → propón un valor basado en el nombre del artículo y tipo de restaurante, \
`confidence: "estimated"`.
  - No acepta → pasa al Paso 3.

**Paso 3:** Confirma que queda pendiente.
  - `purchase_to_stock_factor: null`. El artículo se guarda con factor pendiente.

Nunca llenes un factor sin preguntar primero al operador.

## Reglas generales

- Artículos en la lista de inventario base del contexto son siempre `is_new_item: false`.
- Artículos detectados en el archivo que NO están en la lista base son `is_new_item: true`.
- `category_name` debe ser exactamente `"Perecedero"` o `"No perecedero"`.
- `family_name` debe venir de la lista de familias del contexto; `null` si ninguna aplica.
- Sin alucinaciones: infiere solo del nombre del artículo y tipo de restaurante del contexto.
- El contenido de archivo llega con prefijo `[Contenido de archivo...]` — extrae todos los \
artículos en el mismo turno; no esperes mensajes posteriores.
- Si `recipe_source` es `"file_content"`: el mensaje viene de un archivo; extrae todo en \
ese turno. Si no: el operador describe los artículos en conversación — trata ambos igual.
- Idioma: siempre español. Tono: directo, sin tecnicismos. Máximo 3–4 oraciones en `reply`.
- Formato de respuesta: SIEMPRE JSON con exactamente estos campos (sin agregar ni renombrar):
  {
    "reply": "<texto conversacional, máximo 3-4 oraciones>",
    "proposals": [<lista de artículos — ver estructura abajo>] o null,
    "gap_questions": ["<pregunta de factor pendiente>", ...] o null,
    "needs_supplier_doc": true o null
  }
  Cada elemento de `proposals` tiene exactamente:
  { "name", "stock_unit_symbol", "purchase_unit_symbol", "purchase_to_stock_factor",
    "family_name", "category_name", "confidence", "is_new_item", "description" }
  Nunca uses claves distintas (por ejemplo, no uses "items" en lugar de "proposals"). \
Nunca pongas JSON dentro del campo `reply`.
"""


class _StructuringItemProposal(BaseModel):
    name: str
    stock_unit_symbol: str
    purchase_unit_symbol: str
    purchase_to_stock_factor: float | None
    family_name: str | None = None
    category_name: str
    description: str | None = None
    confidence: str  # "high" | "estimated" | "missing"
    is_new_item: bool


class _StructuringResponse(BaseModel):
    reply: str
    proposals: list[_StructuringItemProposal] | None = None
    needs_supplier_doc: bool | None = None
    gap_questions: list[str] | None = None


@dataclass
class StructuringAgent(BaseAgent):
    """
    Batch-inference agent for the Estructura section.

    Processes all inventory items in a single LLM call and returns structured
    proposals for the editable dataframe. Uses tools to create missing inventory
    units or families after operator confirmation.

    Phase A: Batch inference + unit/family creation via tools.
    Phase B: Factor resolution for purchase ≠ stock items (operator-first).
    Phase C: Table review — handled by the UI, not the agent.

    Input:
        user_message: Message from operator or extracted file content.
        category:     'Perecedero' or 'No perecedero' — current phase.
        recipe_source: Optional — 'file_content' triggers [Contenido de archivo] prefix.

    Output:
        reply:              Conversational response in Spanish.
        proposals:          List of proposal dicts for the dataframe.
        gap_questions:      Factor questions for purchase ≠ stock items.
        needs_supplier_doc: True when agent requests a supplier document.
        raw_response:       Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "Message from operator or extracted file content.",
        "category": "'Perecedero' or 'No perecedero' — current phase.",
        # phase is optional: 'enrich' or 'add'. Omitting it falls back to generic inference.
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply": "Conversational response in Spanish.",
        "proposals": "List of proposal dicts for the dataframe.",
        "gap_questions": "List of factor questions for purchase≠stock items.",
        "needs_supplier_doc": "True when agent requests a supplier document.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _StructuringResponse

    def __post_init__(self) -> None:
        super().__post_init__()
        self.register_tool(
            name="create_inventory_unit",
            func=self._create_inventory_unit_tool,
            description=(
                "Create a new non-standard purchase unit (is_standard=False). "
                "Only call after the operator has explicitly confirmed they want to create it."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Display name for the new unit (e.g. 'caja').",
                    },
                    "symbol": {
                        "type": "string",
                        "description": "Symbol for the unit (e.g. 'caja').",
                    },
                },
                "required": ["name", "symbol"],
            },
        )
        self.register_tool(
            name="create_family_inventory",
            func=self._create_family_inventory_tool,
            description=(
                "Create a new inventory family. "
                "Only call after the operator has explicitly confirmed they want to create it."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Display name for the new family (e.g. 'Cítricos').",
                    },
                },
                "required": ["name"],
            },
        )

    def _create_inventory_unit_tool(self, name: str, symbol: str) -> str:
        """Create a new non-standard inventory unit after operator confirmation.

        Dedup guard: if symbol already exists in DataLake, no insert — returns
        an informational message and ensures symbol is in the context list.
        """
        data_lake = getattr(self, "_data_lake", None)
        if data_lake is None:
            return "Error: data_lake not available — tool called before context was set."

        # Dedup guard: check existing symbols
        existing_symbols: set[str] = set()
        for eid in data_lake.list_entity_ids("inventory_unit"):
            record = data_lake.load_entity("inventory_unit", eid)
            if record and record.get("symbol"):
                existing_symbols.add(record["symbol"])

        ctx = getattr(self, "_context", {})
        if symbol in existing_symbols:
            if symbol not in ctx.get("inventory_units", []):
                ctx.setdefault("inventory_units", []).append(symbol)
            return (
                f"La unidad '{symbol}' ya existe en la configuración "
                "— no es necesario crearla."
            )

        existing_ids = data_lake.list_entity_ids("inventory_unit")
        next_id = max((int(eid) for eid in existing_ids), default=0) + 1
        data_lake.save_entity("inventory_unit", next_id, {
            "id": next_id,
            "name": name,
            "symbol": symbol,
            "description": None,
            "base_unit_id": None,
            "factor_to_base": 1.0,
            "is_standard": False,
        })
        ctx.setdefault("inventory_units", []).append(symbol)
        return f"Unidad '{name}' ({symbol}) creada con id {next_id}."

    def _create_family_inventory_tool(self, name: str) -> str:
        """Create a new inventory family after operator confirmation.

        Dedup guard: if name already exists (case-insensitive) in DataLake,
        no insert — returns an informational message and ensures name is in context.
        """
        data_lake = getattr(self, "_data_lake", None)
        if data_lake is None:
            return "Error: data_lake not available — tool called before context was set."

        # Dedup guard: check existing names (case-insensitive)
        existing_names: dict[str, str] = {}
        for eid in data_lake.list_entity_ids("family_inventory"):
            record = data_lake.load_entity("family_inventory", eid)
            if record and record.get("name"):
                existing_names[record["name"].lower()] = record["name"]

        ctx = getattr(self, "_context", {})
        if name.lower() in existing_names:
            canonical = existing_names[name.lower()]
            if canonical not in ctx.get("families", []):
                ctx.setdefault("families", []).append(canonical)
            return (
                f"La familia '{canonical}' ya existe en la configuración "
                "— no es necesario crearla."
            )

        existing_ids = data_lake.list_entity_ids("family_inventory")
        next_id = max((int(eid) for eid in existing_ids), default=0) + 1
        data_lake.save_entity("family_inventory", next_id, {
            "id": next_id,
            "name": name,
            "description": None,
            "base_unit_id": None,
        })
        ctx.setdefault("families", []).append(name)
        return f"Familia '{name}' creada con id {next_id}."

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        # Store references for tool access during tool calling loop
        self._data_lake = context.get("data_lake")
        self._context = context

        system = _SYSTEM_PROMPT

        # Inject restaurant + session context
        context_parts: list[str] = []
        if context.get("restaurant_name"):
            context_parts.append(f"Restaurante: {context['restaurant_name']}")
        if context.get("restaurant_type"):
            context_parts.append(f"Tipo: {context['restaurant_type']}")
        if context.get("restaurant_description"):
            context_parts.append(f"Descripción: {context['restaurant_description']}")
        if context.get("category"):
            context_parts.append(f"Fase actual: {context['category']}")
        phase = input_data.get("phase")
        if phase:
            context_parts.append(f"Modo del agente: {phase}")
        if context.get("inventory_items"):
            context_parts.append(
                f"Artículos de inventario base ({context.get('category', 'todos')}): "
                + ", ".join(context["inventory_items"])
            )
        if context.get("families"):
            context_parts.append(
                f"Familias de inventario disponibles: {', '.join(context['families'])}"
            )
        if context.get("inventory_units"):
            context_parts.append(
                f"Unidades de inventario disponibles: {', '.join(context['inventory_units'])}"
            )

        if context_parts:
            system = system + "\n\n## Contexto del restaurante\n" + "\n".join(context_parts)

        # Inject accumulated proposals so agent knows what was already proposed
        proposals = self.retrieve("proposals", [])
        if proposals:
            system = (
                system
                + "\n\n## Propuestas ya generadas (no volver a proponer estos artículos)\n"
                + json.dumps(proposals, ensure_ascii=False, indent=2)
            )

        # Build user message
        recipe_source = input_data.get("recipe_source")
        user_msg = input_data["user_message"]
        if recipe_source == "file_content":
            user_msg = f"[Contenido de archivo]\n{user_msg}"

        return system, user_msg

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)
        new_proposals = list(data.get("proposals") or [])
        # Only replace stored proposals when the agent provides new ones.
        # Gap-question resolution turns return proposals=null — preserve the table.
        if new_proposals:
            self.store("proposals", new_proposals)
        proposals = self.retrieve("proposals", [])
        gap_questions = list(data.get("gap_questions") or [])
        self.store("gap_questions", gap_questions)
        return {
            "reply": data.get("reply", ""),
            "proposals": proposals,
            "gap_questions": gap_questions,
            "needs_supplier_doc": data.get("needs_supplier_doc"),
            "raw_response": response,
        }
