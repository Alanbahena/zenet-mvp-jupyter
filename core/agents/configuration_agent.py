"""
ConfigurationAgent — conversational configuration agent for the Configuración section.

Guides the operator through four sequential steps: recipe categories, inventory families,
recipe units, and inventory units. Runs as a single continuous session so context from
earlier steps carries forward. Each turn may update the draft entity list for the current
step and signal readiness via step_complete. Persistence to DataLake is handled by the
section UI (subtask 9.3), not by this agent.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent
from core.domain.data_model import (
    get_category_recipe_template,
    get_family_inventory_template,
    get_inventory_unit_template,
    get_recipe_unit_template,
)


_SYSTEM_PROMPT = """Eres Zeni, el asistente de configuración de Zenet.

Tu objetivo es guiar al operador del restaurante a través de la configuración estructural \
de su modelo de datos: categorías de recetas, familias de inventario, unidades de receta \
y unidades de inventario — todo en una sola conversación continua.

## Para qué sirve cada entidad

**Categorías de recetas**
Agrupan las recetas por tipo de servicio o turno (ej. Desayunos, Comidas, Cenas, Bebidas).

**Familias de inventario**
Agrupan los ingredientes por tipo de producto (ej. Lácteos, Carnes, Verduras).

**Unidades de receta**
Son las unidades que aparecen dentro de las listas de ingredientes de las recetas
(ej. g, kg, taza, cucharada). Deben coincidir con la forma en que están escritas las recetas.

**Unidades de inventario**
Son las unidades que se usan al comprar y controlar el stock (ej. kg, L, caja, bolsa).
Las unidades estándar (kg, g, L, ml, pza) tienen conversiones universales.
Las unidades no estándar (caja, bolsa, bote) se vincularán a unidades estándar más adelante.

## Comportamiento según nivel de estandarización

**Nivel 1 — Operación en la cabeza**
El operador probablemente no tiene listas existentes. Recorre la plantilla paso a paso.
Explica para qué sirve cada elemento sugerido. Invita a agregar o quitar.
Sé alentador — probablemente es la primera vez que estructuran esto.

**Nivel 2/3 — Parcialmente documentado / Estructurado**
El operador ya tiene contexto. Presenta la plantilla como "lo que Zenet sugiere para tu
tipo de restaurante" y pide confirmación, ajustes o adiciones. Sé más conciso.

## Reglas de conversación

- Siempre en español. Tono cercano y directo — como un colega con experiencia, no un formulario.
- 2–4 oraciones por respuesta. Nunca listes todo de golpe sin preguntar primero.
- Trabaja en exactamente un paso a la vez. No hagas referencia a otro paso hasta que el
  actual esté confirmado.
- Cuando el operador esté satisfecho (confirma, dice "sí", "bien", "así está bien",
  "continúa") o quiera saltarse el paso: establece `step_complete: true`.
- Si el operador quiere saltarse sin revisar: acepta la plantilla tal como está,
  coloca la lista de plantilla en `entities` y establece `step_complete: true`.
- Si el operador pregunta para qué sirve algo: explícalo en 1–2 oraciones en lenguaje simple.

## Campo description (aplica a los cuatro tipos de entidad)

- Siempre llena el campo `description` para cada entidad propuesta — nunca lo dejes en null
  a menos que el operador lo pida explícitamente.
- La descripción debe ser una frase corta en lenguaje simple. Sin mencionar costos,
  cálculos internos ni terminología de Zenet. Infíerela del contexto.
- Máximo una línea por tipo:
  - Categoría: qué recetas pertenecen aquí. Ej: "Platillos del turno de mañana".
  - Familia: qué ingredientes entran aquí. Ej: "Productos de origen animal con grasa o proteína láctea".
  - Unidad de receta: qué mide o para qué se usa en recetas. Ej: "Medida de volumen pequeña para \
líquidos y sólidos". No menciones equivalencias — la conversión de unidades de receta depende \
del ingrediente, no de la unidad.
  - Unidad de inventario estándar: qué mide. Ej: "Unidad de masa del sistema métrico".
  - Unidad de inventario no estándar (`is_standard: false`): describe el envase o presentación \
del proveedor e indica que la equivalencia se definirá más adelante. \
Ej: "Caja del proveedor — equivalencia con unidad estándar por definir más adelante".

## Campo symbol (aplica a unidades de receta y unidades de inventario)

- Siempre llena el campo `symbol` — nunca lo dejes vacío ni en null.
- Usa la abreviatura estándar o la más común en cocina profesional.
  Ejemplos: gramo → g, kilogramo → kg, litro → L, mililitro → ml, pieza → pza,
  cucharada → cda, cucharadita → cdta, taza → tza, onza → oz, libra → lb.

## Transición entre pasos

Cuando el operador confirma un paso, recibirás el mensaje "__confirmed__". Responde con:
- Una frase corta que reconozca el paso completado.
- Una introducción breve al siguiente paso: para qué sirve y la plantilla sugerida como punto de partida.
- Una pregunta concreta para iniciar la conversación del nuevo paso.
Máximo 3 oraciones. No repitas toda la plantilla de golpe — menciona 2 o 3 ejemplos y pregunta si quieren ajustar.

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos tres campos:
- "reply": tu respuesta conversacional (nunca JSON dentro de este campo)
- "entities": la lista propuesta de entidades para el paso actual como array de objetos,
  o null si no hay cambios respecto al borrador anterior
- "step_complete": true cuando el operador ha confirmado el paso actual, null en caso contrario
"""


_STEP_TEMPLATE_MAP: dict[str, Any] = {
    "categories":      get_category_recipe_template,
    "families":        get_family_inventory_template,
    "recipe_units":    get_recipe_unit_template,
    "inventory_units": get_inventory_unit_template,
}

_STEP_LABELS: dict[str, str] = {
    "categories":      "Categorías de recetas",
    "families":        "Familias de inventario",
    "recipe_units":    "Unidades de receta",
    "inventory_units": "Unidades de inventario",
}

_FALLBACK_REPLY = (
    "Hubo un problema al procesar la respuesta. Por favor intenta de nuevo."
)


class _ConfigurationResponse(BaseModel):
    """Structured response: conversational reply + entity list + step completion signal."""

    reply: str
    entities: list[dict] | None = None
    step_complete: bool | None = None


class ConfigurationAgent(BaseAgent):
    """
    Conversational configuration agent for the Configuración section.

    Guides the operator through four sequential steps: recipe categories,
    inventory families, recipe units, and inventory units. Runs as a single
    continuous session so context from earlier steps carries forward.

    Each turn may update the draft entity list for the current step via the
    `entities` field and signal readiness via `step_complete`. The UI uses
    `step_complete` to enable the confirm button; confirmed entities are
    persisted to DataLake by the section UI (not by this agent).

    Input:
        user_message: A message from the restaurant operator.

    Context (all provided by the section UI before calling run()):
        restaurant_type_id:    int  — used to load the correct template
        restaurant_type:       str  — injected into prompt for display
        restaurant_name:       str  — injected into prompt for display
        standardization_level: int  — controls agent tone (1 vs 2/3)
        current_step:          str  — "categories" | "families" |
                                      "recipe_units" | "inventory_units"

    Output:
        reply:         Conversational response shown to the operator.
        entities:      Proposed entity list for the current step, or None.
        step_complete: True when agent judges current step ready to confirm.
        raw_response:  Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply":         "Conversational response shown to the operator.",
        "entities":      "Proposed entity list for current step, or None if no update.",
        "step_complete": "True when agent judges current step ready to confirm.",
        "raw_response":  "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _ConfigurationResponse

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        restaurant_type_id: int = context.get("restaurant_type_id", 1)
        restaurant_type: str = context.get("restaurant_type", "")
        restaurant_name: str = context.get("restaurant_name", "")
        level: int = context.get("standardization_level", 1)
        current_step: str = context.get("current_step", "categories")

        # Store current_step so _process_response() knows which key to write to.
        # _process_response() receives only the response string — no context.
        self.store("current_step", current_step)

        # Load template for current step and format as a readable list for the prompt.
        template_fn = _STEP_TEMPLATE_MAP.get(current_step)
        template_items = template_fn(restaurant_type_id) if template_fn else ()
        template_lines = []
        for item in template_items:
            if hasattr(item, "symbol"):
                template_lines.append(f"- {item.name} ({item.symbol})")
            else:
                template_lines.append(f"- {item.name}")
        template_preview = (
            "\n".join(template_lines) if template_lines else "(sin plantilla)"
        )

        # Build context block appended to the system prompt.
        context_parts: list[str] = ["## Contexto del operador"]
        if restaurant_name:
            context_parts.append(f"Restaurante: {restaurant_name}")
        if restaurant_type:
            context_parts.append(f"Tipo: {restaurant_type}")
        context_parts.append(f"Nivel de estandarización: {level}")
        context_parts.append(
            f"Paso actual: {_STEP_LABELS.get(current_step, current_step)}\n"
            f"Plantilla sugerida:\n{template_preview}"
        )

        # Inject existing draft if the operator has already built a list this session.
        existing = self.retrieve(current_step)
        if existing:
            context_parts.append(
                "Borrador actual (ya revisado en esta conversación):\n"
                + json.dumps(existing, ensure_ascii=False, indent=2)
            )

        system = _SYSTEM_PROMPT + "\n\n" + "\n\n".join(context_parts)
        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)

        # Retrieve the step that was active when _generate_prompt() ran.
        current_step = self.retrieve("current_step")
        entities = data.get("entities")

        # Only overwrite the stored draft when the LLM returned a non-null entities list.
        # None means "no change" — the existing draft is preserved.
        if entities is not None and current_step is not None:
            self.store(current_step, entities)

        # Fallback reply when _parse_response() returns {} (malformed JSON from LLM).
        reply = data.get("reply") or _FALLBACK_REPLY

        return {
            "reply":         reply,
            "entities":      entities,
            "step_complete": data.get("step_complete"),
            "raw_response":  response,
        }
