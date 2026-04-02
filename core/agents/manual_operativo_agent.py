from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent


class ManualOperativoAgent(BaseAgent):
    """
    Read-only conversational agent for the Manual Operativo section.

    Answers natural language Q&A about the restaurant's data and performs
    ingredient deduction calculations. Never modifies DataLake.

    Receives the full restaurant manual as structured plain text injected into
    the system prompt via context["manual_context"]. No tool calls needed for MVP.
    """

    INPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "user_message": "Operator question or deduction request in natural language.",
    }
    OUTPUT_SCHEMA: ClassVar[dict[str, str]] = {
        "reply": "Agent response in Spanish.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = None  # plain prose

    def _generate_prompt(
        self, input_data: dict[str, Any], context: dict[str, Any]
    ) -> tuple[str, str]:
        manual_text = context.get("manual_context", "")
        system = (
            "Eres el Asistente Operativo de Zenet. Tienes acceso completo al manual "
            "operativo del restaurante que se muestra a continuación. Responde siempre "
            "en español, de forma clara y directa para un operador de restaurante.\n\n"
            "Puedes:\n"
            "- Responder preguntas sobre los datos del restaurante (recetas, inventario, "
            "configuración, calificación de estandarización)\n"
            "- Calcular deducciones de ingredientes: si el operador pregunta cuánto "
            "necesita para N porciones de un platillo, multiplica las cantidades de la "
            "receta por N. Para ingredientes con unidad de compra distinta a la unidad "
            "de stock, calcula también las unidades de compra necesarias usando el "
            "factor de conversión. Indica explícitamente los ingredientes sin vínculo "
            "de inventario.\n"
            "- Explicar qué se necesita para mejorar la calificación de estandarización\n\n"
            "No puedes modificar datos. Si el operador pide hacer un cambio, "
            "indícale que regrese a la sección correspondiente del notebook.\n\n"
            f"MANUAL OPERATIVO DEL RESTAURANTE\n"
            f"{'=' * 40}\n"
            f"{manual_text}"
        )
        return system, input_data["user_message"]

    def _process_response(self, response: str) -> dict[str, Any]:
        return {"reply": response, "raw_response": response}
