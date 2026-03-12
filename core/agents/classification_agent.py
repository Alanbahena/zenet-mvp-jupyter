"""
ClassificationAgent -- conversational diagnosis agent for the Clasificación section.

Identifies the operator's standardization level (1–3) through a short conversation.
The diagnosed level is stored in _data_store and persisted to DataLake only when the
operator confirms via the UI (subtask 8.4). Tasks 9–12 load this level to calibrate
their agents' tone, suggestions, and approach.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel, field_validator

from core.agents.base_agent import BaseAgent


_SYSTEM_PROMPT = """Eres Zeni, el asistente de clasificación de Zenet.

Tu objetivo es entender cómo opera el restaurante hoy para asignarle un nivel de
estandarización (1, 2 o 3). Este nivel le permitirá a Zenet calibrar su enfoque
y sugerencias en cada sección del sistema.

## Los tres niveles de estandarización

**Nivel 1 — Operación en la cabeza**
Todo está en la memoria del operador o del equipo. No hay recetas escritas, ni listas
de inventario, ni procesos documentados. El equipo trabaja por costumbre.
→ Zenet construirá todo desde plantillas base y guiará cada paso.

**Nivel 2 — Parcialmente documentado**
Existe algo escrito: un Excel, fotos de recetas, notas sueltas, listas parciales de
inventario. No está completo ni estructurado, pero hay material con qué trabajar.
→ Zenet usará lo que haya y complementará con plantillas donde falte.

**Nivel 3 — Operación estructurada**
La mayoría de categorías, recetas e inventario están documentados. Puede ser en Excel,
PDF o sistema — está organizado y relativamente completo.
→ Zenet importará y normalizará la información existente.

## Diagnóstico del nivel (2–3 preguntas, usa tu criterio)

Usa estas preguntas para entender el estado general de la operación. No tienes que
hacer todas — elige las que aporten más contexto:

- ¿Cuántos años lleva operando el restaurante?
- Del 1 al 10, ¿qué tan estandarizada sientes tu operación hoy?
- Si te vas un fin de semana, ¿la operación funciona sin ti?
- Cuando entra un empleado nuevo, ¿cómo aprende el trabajo?

## Operador que quiere saltarse el proceso

Si el operador señala que quiere avanzar sin responder preguntas — por ejemplo dice
"no sé, configúralo tú" o "empieza ya" o "no tengo tiempo" — debes:
1. Proponer Nivel 1 como punto de partida seguro
2. Explicar que Zenet lo acompañará paso a paso desde las plantillas base
3. Invitarlo a corregirlo si algo no cuadra con su realidad

## Reglas de comunicación

- Siempre en español
- Tono cercano y directo, sin tecnicismos — como alguien que ya pasó por esto
- 2–4 oraciones por respuesta
- Propone el nivel en cuanto tengas confianza — no esperes a hacer todas las preguntas posibles
- No acumules preguntas: haz una a la vez
- El campo reply debe ser texto conversacional, no JSON
"""


class _ClassificationResponse(BaseModel):
    """Hybrid response: conversational reply + structured standardization level."""

    reply: str
    standardization_level: int | None = None

    @field_validator("standardization_level")
    @classmethod
    def validate_level(cls, v: int | None) -> int | None:
        if v is not None and v not in {1, 2, 3}:
            return None
        return v


class ClassificationAgent(BaseAgent):
    """
    Conversational diagnosis agent for the Clasificación section.

    Identifies the operator's standardization level (1–3) through a short conversation.
    Accumulates the diagnosed level in _data_store across turns. Nothing is persisted
    to DataLake until the operator confirms via the Confirm button in the UI.

    The diagnosed level is used by Tasks 9–12 agents to calibrate their tone,
    suggestions, and approach for each section of the pipeline.

    Input:
        user_message: A message from the restaurant operator.

    Output:
        reply:                 Conversational response shown to the operator.
        standardization_level: Diagnosed level (1/2/3) or None if not yet determined.
        raw_response:          Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply":                 "Conversational response shown to the operator.",
        "standardization_level": "Diagnosed level (1/2/3) or None if not yet determined.",
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
        level = self.retrieve("standardization_level")
        if level is not None:
            system = (
                system
                + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
                + json.dumps({"standardization_level": level}, ensure_ascii=False)
            )

        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)

        # standardization_level: store only if non-None
        level = data.get("standardization_level")
        if level is not None:
            self.store("standardization_level", level)

        return {
            "reply":                 data.get("reply", ""),
            "standardization_level": data.get("standardization_level"),
            "raw_response":          response,
        }
