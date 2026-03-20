"""
ClassificationAgent -- conversational diagnosis agent for the Clasificación section.

Identifies the operator's standardization level (1–3) through a short conversation,
then asks for a brief restaurant description. The agent enriches the operator's input
into a structured profile for downstream agent consumption.

Both the diagnosed level and the restaurant description are stored in _data_store and
persisted to DataLake only when the operator confirms via the UI. Tasks 9–12 load
these values to calibrate their agents' tone, suggestions, and approach.
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
hacer todas — elige las que aporten más contexto o crea las que consideres importantes para el diagnóstico:

- ¿Cuántos años lleva operando el restaurante?
- Del 1 al 10, ¿qué tan estandarizada sientes tu operación hoy?
- Si te vas un fin de semana, ¿la operación funciona sin ti?
- Cuando entra un empleado nuevo, ¿cómo aprende el trabajo?
- Tus recetas se utilizan con la cantidad y unidad correcta?
- Tus inventarios se utilizan con la cantidad y unidad correcta?


## Operador que quiere saltarse el proceso

Si el operador señala que quiere avanzar sin responder preguntas — por ejemplo dice
"no sé, configúralo tú" o "empieza ya" o "no tengo tiempo" — debes:
1. Proponer Nivel 1 como punto de partida seguro
2. Explicar que Zenet lo acompañará paso a paso desde las plantillas base
3. Invitarlo a corregirlo si algo no cuadra con su realidad

## Descripción del restaurante

Una vez que hayas diagnosticado el nivel de estandarización (standardization_level no es null), \
pregunta al operador que describa brevemente su restaurante: tipo de comida que sirve \
(mexicana, mariscos, hamburguesas, italiana, etc.), estilo de servicio y tamaño aproximado. \
La pregunta debe incluir un ejemplo visible de cómo responder, así: \
"Cuéntame sobre tu restaurante. Por ejemplo: 'Comida mexicana tradicional, servicio en \
mostrador, unas 30 sillas.' ¿Cómo describirías el tuyo?"

Después de que el operador responda, sintetiza un perfil completo del restaurante en el \
campo "description". Combina lo que el operador dijo con lo que ya sabes de la conversación \
(nombre, tipo de restaurante, nivel de estandarización). El resultado debe ser una \
descripción estructurada y clara, optimizada para que otros agentes del sistema la lean.

Guarda también las palabras exactas del operador en el campo "description_raw" — sin \
modificar, sin expandir, tal cual las escribió.

REGLA ABSOLUTA: Usa SOLO información que el operador haya proporcionado explícitamente \
o que esté en el contexto inyectado (nombre y tipo de restaurante). No inventes, no asumas, \
no infieras datos que no se hayan dicho. Si el operador dio poca información, la descripción \
debe ser corta y fiel — es preferible una descripción breve y precisa que una larga e inventada.

Si el operador no quiere responder o dice que no sabe, acepta y deja description y \
description_raw en null. No insistas — una sola pregunta es suficiente.

Una vez que hayas guardado la descripción (o el operador haya declinado responderla), \
incluye al final de tu respuesta: "Ya puedes hacer clic en **Confirmar clasificación** \
para continuar con el siguiente paso."

## Reglas de comunicación

- Siempre en español
- Tono cercano y directo, sin tecnicismos — como alguien que ya pasó por esto
- 2–4 oraciones por respuesta
- Propone el nivel en cuanto tengas confianza — no esperes a hacer todas las preguntas posibles
- No acumules preguntas: haz una a la vez

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos campos:
- "reply": tu respuesta conversacional en texto (nunca JSON dentro de este campo)
- "standardization_level": el nivel diagnosticado (1, 2 o 3), o null si aún no tienes suficiente información
- "description": perfil enriquecido del restaurante sintetizado a partir de la conversación, o null si aún no se ha capturado
- "description_raw": las palabras exactas del operador describiendo su restaurante, o null si aún no se ha capturado
"""


class _ClassificationResponse(BaseModel):
    """Hybrid response: conversational reply + structured standardization level + restaurant description."""

    reply: str
    standardization_level: int | None = None
    description: str | None = None
    description_raw: str | None = None

    @field_validator("standardization_level")
    @classmethod
    def validate_level(cls, v: int | None) -> int | None:
        if v is not None and v not in {1, 2, 3}:
            return None
        return v


class ClassificationAgent(BaseAgent):
    """
    Conversational diagnosis agent for the Clasificación section.

    Identifies the operator's standardization level (1–3) through a short conversation,
    then asks for a brief restaurant description. The agent enriches the operator's raw
    input into a structured profile optimized for downstream agent consumption. Only
    information explicitly provided by the operator or present in the injected context
    is used — the agent never invents or assumes data.

    Accumulates diagnosed level and restaurant description in _data_store across turns.
    Nothing is persisted to DataLake until the operator confirms via the Confirm button.

    Input:
        user_message: A message from the restaurant operator.

    Output:
        reply:                      Conversational response shown to the operator.
        standardization_level:      Diagnosed level (1/2/3) or None if not yet determined.
        restaurant_description:     Agent-enriched restaurant profile or None.
        restaurant_description_raw: Operator's exact words or None.
        raw_response:               Full LLM response string.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "A message from the restaurant operator.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply":                      "Conversational response shown to the operator.",
        "standardization_level":      "Diagnosed level (1/2/3) or None if not yet determined.",
        "restaurant_description":     "Agent-enriched restaurant profile or None.",
        "restaurant_description_raw": "Operator's exact words describing the restaurant or None.",
        "raw_response":               "Full LLM response string.",
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
        description = self.retrieve("restaurant_description")
        draft: dict[str, Any] = {}
        if level is not None:
            draft["standardization_level"] = level
        if description is not None:
            draft["restaurant_description"] = description
        if draft:
            system = (
                system
                + "\n\n## Borrador actual (ya capturado en esta conversación)\n"
                + json.dumps(draft, ensure_ascii=False)
            )

        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)

        # standardization_level: store only if non-None
        level = data.get("standardization_level")
        if level is not None:
            self.store("standardization_level", level)

        # restaurant description: store enriched + raw when provided
        description = data.get("description")
        if description is not None:
            self.store("restaurant_description", description)
        description_raw = data.get("description_raw")
        if description_raw is not None:
            self.store("restaurant_description_raw", description_raw)

        return {
            "reply":                      data.get("reply", ""),
            "standardization_level":      data.get("standardization_level"),
            "restaurant_description":     data.get("description"),
            "restaurant_description_raw": data.get("description_raw"),
            "raw_response":               response,
        }
