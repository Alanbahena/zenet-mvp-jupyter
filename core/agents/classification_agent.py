"""
ClassificationAgent -- conversational diagnosis agent for the Clasificación section.

Identifies the operator's standardization level (1–3) and which of the four sections
(recipe_categories, inventory_families, recipes, inventory) have existing documentation.
Accumulates a classification draft across turns via _data_store. Nothing is persisted
to DataLake until the operator confirms via the UI (subtask 8.4).
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel, field_validator

from core.agents.base_agent import BaseAgent


_SYSTEM_PROMPT = """Eres Zeni, el asistente de clasificación de Zenet.

Tu objetivo es entender cómo opera el restaurante hoy para asignarle un nivel de
estandarización (1, 2 o 3) y determinar qué información ya tiene documentada en cada
una de las cuatro secciones del sistema.

## Los tres niveles de estandarización

**Nivel 1 — Operación en la cabeza**
Todo está en la memoria del operador o del equipo. No hay recetas escritas, ni listas
de inventario, ni procesos documentados. El equipo trabaja por costumbre.
→ Zenet construirá todo desde plantillas base.

**Nivel 2 — Parcialmente documentado**
Existe algo escrito: un Excel, fotos de recetas, notas sueltas, listas parciales de
inventario. No está completo ni estructurado, pero hay material con qué trabajar.
→ Zenet usará lo que haya y complementará con plantillas donde falte.

**Nivel 3 — Operación estructurada**
La mayoría de categorías, recetas e inventario están documentados. Puede ser en Excel,
PDF o sistema — está organizado y relativamente completo.
→ Zenet importará y normalizará la información existente.

## Las cuatro secciones que debes evaluar

Para cada una necesitas determinar si el operador ya tiene información (has_data: true)
o si necesitará usar las plantillas base de Zenet (has_data: false):

- **recipe_categories**: Categorías de recetas (ej. Entradas, Platos fuertes, Postres, Bebidas)
- **inventory_families**: Familias de inventario (ej. Carnes, Lácteos, Verduras, Abarrotes)
- **recipes**: Recetas con ingredientes y cantidades documentadas
- **inventory**: Artículos de inventario con unidades y proveedores

## Fase 1 — Diagnóstico del nivel (2–3 preguntas, usa tu criterio)

Usa estas preguntas para entender el estado general de la operación antes de entrar
al detalle por sección. No tienes que hacer todas — elige las que aporten más contexto:

- ¿Cuántos años lleva operando el restaurante?
- Del 1 al 10, ¿qué tan estandarizada sientes tu operación hoy?
- Si te vas un fin de semana, ¿la operación funciona sin ti?
- Cuando entra un empleado nuevo, ¿cómo aprende el trabajo?

## Fase 2 — Verificación por sección (las 4 son obligatorias)

Antes de proponer una clasificación final, debes tener un valor has_data para cada
una de las cuatro secciones. Puedes mezclar estas preguntas con las de la Fase 1
de forma natural — no tiene que ser en dos rondas separadas:

- ¿Tienes tus categorías de recetas definidas? (ej. Entradas, Platos fuertes)
- ¿Tienes familias de inventario definidas? (ej. Carnes, Lácteos, Verduras)
- ¿Tienes recetas escritas con ingredientes, cantidades y unidades?
- ¿Tienes una lista de inventario con unidades y proveedores?

## Operador que quiere saltarse el proceso

Si el operador señala que quiere avanzar sin responder preguntas — por ejemplo dice
"no sé, configúralo tú" o "empieza ya" o "no tengo tiempo" — debes:
1. Proponer Nivel 1 con todas las secciones como has_data: false
2. Explicar que este es un punto de partida seguro — todas las plantillas base estarán disponibles
3. Invitarlo a corregirlo si algo no cuadra con su realidad

## Reglas de comunicación

- Siempre en español
- Tono cercano y directo, sin tecnicismos — como alguien que ya pasó por esto
- 2–4 oraciones por respuesta
- Propone el nivel en cuanto tengas confianza — no esperes a hacer todas las preguntas posibles
- No acumules preguntas: haz una a la vez
- El campo reply debe ser texto conversacional, no JSON
"""


class _SectionStatus(BaseModel):
    """Documentation status for a single section."""

    has_data: bool


class _ClassificationResponse(BaseModel):
    """Hybrid response: conversational reply + structured classification fields."""

    reply: str
    standardization_level: int | None = None
    sections: dict[str, _SectionStatus] | None = None

    @field_validator("standardization_level")
    @classmethod
    def validate_level(cls, v: int | None) -> int | None:
        if v is not None and v not in {1, 2, 3}:
            return None
        return v


class ClassificationAgent(BaseAgent):
    """
    Conversational diagnosis agent for the Clasificación section.

    Identifies the operator's standardization level (1–3) and which sections
    have existing documentation. Accumulates a draft in _data_store across turns
    via two-phase conversation: level diagnosis (broad questions) followed by
    section-by-section documentation check. Nothing is persisted to DataLake
    until the operator confirms via the Confirm button in the UI.

    Input:
        user_message: A message from the restaurant operator.

    Output:
        reply:                 Conversational response shown to the operator.
        standardization_level: Diagnosed level (1/2/3) or None if not yet determined.
        sections:              Dict of section has_data flags or None.
        raw_response:          Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply":                 "Conversational response shown to the operator.",
        "standardization_level": "Diagnosed level (1/2/3) or None if not yet determined.",
        "sections":              "Dict of section has_data flags or None.",
        "raw_response":          "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _ClassificationResponse

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        system = _SYSTEM_PROMPT

        # 1. Inject restaurant context if available
        context_lines: list[str] = []
        if context.get("restaurant_name"):
            context_lines.append(f"El restaurante se llama {context['restaurant_name']}.")
        if context.get("restaurant_type"):
            context_lines.append(f"Es un restaurante de tipo {context['restaurant_type']}.")
        if context_lines:
            system = system + "\n\n## Contexto del restaurante\n" + "\n".join(context_lines)

        # 2. Inject current draft so agent knows what has already been captured
        current_draft: dict[str, Any] = {}
        level = self.retrieve("standardization_level")
        sections = self.retrieve("sections")
        if level is not None:
            current_draft["standardization_level"] = level
        if sections is not None:
            current_draft["sections"] = sections
        if current_draft:
            system = (
                system
                + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
                + json.dumps(current_draft, ensure_ascii=False, indent=2)
            )

        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)

        # standardization_level: store only if non-None
        level = data.get("standardization_level")
        if level is not None:
            self.store("standardization_level", level)

        # sections: deep-merge at key level — never replace the whole dict
        # Serialize _SectionStatus objects to plain dicts for storage
        sections = data.get("sections")
        if sections is not None:
            sections_plain = {k: {"has_data": v.has_data} for k, v in sections.items()}
            existing = self.retrieve("sections") or {}
            existing.update(sections_plain)
            self.store("sections", existing)

        return {
            "reply":                 data.get("reply", ""),
            "standardization_level": data.get("standardization_level"),
            "sections":              data.get("sections"),
            "raw_response":          response,
        }
