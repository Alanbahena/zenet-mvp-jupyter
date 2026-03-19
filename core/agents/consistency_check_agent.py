"""
ConsistencyCheckAgent — structural validation agent for the Configuración section.

Checks entity lists for structural gaps (per-step) and cross-entity inconsistencies
(final). Called by the section UI (subtask 9.3) before the operator confirms each
step and before the last step is saved.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel

from core.agents.base_agent import BaseAgent


_PER_STEP_SYSTEM_PROMPT = """Eres un validador estructural para Zenet, un sistema operativo para restaurantes.

Recibirás un JSON con tres campos:
- "step": el paso que se está validando ("categories", "families", "recipe_units" o "inventory_units")
- "entities": la lista de entidades propuestas por el operador
- "restaurant_type": el tipo de restaurante (ej. "Casual", "Rápida", "Gourmet", "Cafetería")

Tu tarea es revisar si la lista tiene huecos estructurales para ese tipo de restaurante.
No juzgues el estilo ni el nombre — solo identifica lo que falta o está mal configurado.

## Criterios por paso

**categories (Categorías de recetas)**
- ¿Hay al menos una categoría para comida sólida y una para bebidas?
- ¿Falta alguna categoría obvia para el tipo de restaurante?
  (ej. un café sin "Bebidas calientes", un restaurante casual sin "Comidas")
- ¿Hay menos de 2 categorías en total?

**families (Familias de inventario)**
- ¿Hay al menos una familia para productos perecederos (Carnes, Lácteos, Verduras, Frutas)?
- ¿Hay al menos una familia para no perecederos (Granos, Abarrotes, Condimentos)?
- ¿Falta alguna familia crítica para el tipo de restaurante?
  (ej. un café sin "Bebidas calientes" o "Lácteos", un gourmet sin "Mariscos" o "Vinos")
- ¿Hay menos de 3 familias en total?

**recipe_units (Unidades de receta)**
- ¿Hay al menos una unidad de peso (g o kg)?
- ¿Hay al menos una unidad de volumen (ml o L)?
- ¿Hay al menos una unidad de conteo (pza, pieza o similar)?
- ¿Hay unidades duplicadas (mismo nombre o símbolo)?

**inventory_units (Unidades de inventario)**
- ¿Hay al menos una unidad estándar de peso (kg o g, is_standard: true)?
- ¿Hay al menos una unidad estándar de volumen (L o ml, is_standard: true)?
- ¿Hay unidades no estándar sin descripción que mencione "equivalencia"?
- ¿Hay unidades duplicadas (mismo nombre o símbolo)?

## Relevancia semántica

Verifica que cada entidad tenga el tipo correcto para el paso. Marca como issue bloqueante
cualquier entidad que claramente no pertenezca a ese paso.

**categories**: deben ser tipos de servicio o turnos de comida (ej. Desayunos, Comidas, Cenas,
Bebidas, Postres). NO son válidos: ingredientes (azúcar, pollo), platillos (tacos, pizza),
familias de inventario (Lácteos, Carnes), unidades de medida (kg, taza).

**families**: deben ser grupos de ingredientes por tipo de producto (ej. Lácteos, Carnes,
Verduras, Frutas, Granos). NO son válidos: turnos de comida (Desayunos, Comidas),
platillos, unidades de medida, ingredientes individuales (azúcar, sal).

**recipe_units**: deben ser unidades de medida usadas en recetas (ej. g, kg, taza, cucharada,
ml, pieza). NO son válidos: ingredientes, categorías de recetas, familias de inventario,
nombres de platillos.

**inventory_units**: deben ser unidades de compra o presentaciones de proveedor (ej. kg, L,
caja, bolsa, bote, pieza). NO son válidos: ingredientes, categorías, familias, platillos.

## Reglas

- `issues`: problemas bloqueantes — la configuración producirá errores o datos incompletos.
- `suggestions`: mejoras opcionales — la configuración funciona pero podría ser más completa.
- `looks_good`: true si no hay issues (puede haber suggestions); false si hay al menos un issue.
- Si la lista tiene 0 entidades: ese es siempre un issue bloqueante.
- No inventes checks fuera de los criterios listados arriba.
- Responde siempre en español.

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos tres campos:
- "issues": array de strings con los problemas bloqueantes encontrados (vacío si ninguno)
- "suggestions": array de strings con mejoras opcionales (vacío si ninguna)
- "looks_good": true si no hay issues, false si hay al menos uno"""


_FINAL_SYSTEM_PROMPT = """Eres un validador estructural para Zenet, un sistema operativo para restaurantes.

Recibirás un JSON con cinco campos:
- "categories": lista de categorías de recetas configuradas
- "families": lista de familias de inventario configuradas
- "recipe_units": lista de unidades de receta configuradas
- "inventory_units": lista de unidades de inventario configuradas
- "restaurant_type": el tipo de restaurante

Tu tarea es revisar si las cuatro listas son consistentes entre sí.
No repitas los checks individuales de cada lista — ya fueron validados.
Busca únicamente inconsistencias que solo se ven cuando las cuatro listas se ven juntas.

## Criterios de consistencia cruzada

**Unidades de receta vs unidades de inventario**
- ¿Hay unidades de receta volumétricas no estándar (taza, cucharada, cucharadita)
  pero ninguna unidad de inventario de volumen estándar (L, ml)?
  → El sistema no podrá normalizar esas cantidades.
- ¿Hay unidades de receta de conteo no estándar (pieza, tortilla, rebanada)
  pero ninguna unidad de inventario de conteo (pza)?
  → Ingredientes en esas unidades quedarán sin normalizar.

**Familias vs categorías de recetas**
- ¿Hay categorías de recetas configuradas pero 0 familias de inventario?
  → Zenet no podrá asignar ingredientes a familias al procesar recetas.
- ¿Hay familias de inventario configuradas pero 0 categorías de recetas?
  → Los reportes de costo por categoría no tendrán datos.

**Cobertura general**
- ¿Alguna de las cuatro listas quedó completamente vacía?
  → Es un issue bloqueante independientemente de las demás.

## Reglas

- `issues`: inconsistencias que causarán problemas reales en normalización o reportes.
- `suggestions`: mejoras opcionales de alineación entre listas.
- `looks_good`: true si no hay issues; false si hay al menos uno.
- No repitas issues que ya se detectaron en los checks individuales por paso.
- No inventes checks fuera de los criterios listados arriba.
- Responde siempre en español.

## Formato de respuesta

Responde SIEMPRE con JSON usando exactamente estos tres campos:
- "issues": array de strings con inconsistencias bloqueantes (vacío si ninguna)
- "suggestions": array de strings con mejoras opcionales (vacío si ninguna)
- "looks_good": true si no hay issues, false si hay al menos uno"""


class _ConsistencyCheckResponse(BaseModel):
    issues: list[str]       # blocking structural gaps
    suggestions: list[str]  # optional improvements
    looks_good: bool        # True if no blocking issues; always present


class ConsistencyCheckAgent(BaseAgent):
    """
    Structural validation agent for the Configuración section.

    Called by the section UI (subtask 9.3) in two distinct modes:

    Per-step mode — called before the operator confirms each step:
        Input: {"step": str, "entities": list[dict], "restaurant_type": str}
        Checks a single entity list for structural gaps.

    Final cross-entity mode — called before the last step is saved:
        Input: {"categories": list, "families": list,
                "recipe_units": list, "inventory_units": list,
                "restaurant_type": str}
        Checks all four lists together for cross-entity inconsistencies.

    INPUT_SCHEMA is empty ({}) to disable validation — the two call shapes
    have incompatible keys and cannot share a single schema.

    This agent is stateless: no store()/retrieve(), no save_state()/load_state().
    Each call is fully independent.

    Output:
        issues:       List of blocking structural gaps found.
        suggestions:  List of optional improvements.
        looks_good:   True if no blocking issues found.
        raw_response: Full LLM response string.
    """

    INPUT_SCHEMA:   ClassVar[dict[str, str]] = {}
    OUTPUT_SCHEMA:  ClassVar[dict[str, str]] = {
        "issues":       "List of blocking structural gaps found.",
        "suggestions":  "List of optional improvements.",
        "looks_good":   "True if no blocking issues found.",
        "raw_response": "Full LLM response string.",
    }
    RESPONSE_MODEL: ClassVar[type[BaseModel] | None] = _ConsistencyCheckResponse

    def _generate_prompt(
        self,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> tuple[str, str]:
        if "step" in input_data:
            # Per-step call: validate a single entity list
            system = _PER_STEP_SYSTEM_PROMPT
            user = json.dumps({
                "step":            input_data["step"],
                "entities":        input_data.get("entities", []),
                "restaurant_type": input_data.get("restaurant_type", ""),
            }, ensure_ascii=False)
        else:
            # Final cross-entity call: validate all four lists together
            system = _FINAL_SYSTEM_PROMPT
            user = json.dumps({
                "categories":      input_data.get("categories", []),
                "families":        input_data.get("families", []),
                "recipe_units":    input_data.get("recipe_units", []),
                "inventory_units": input_data.get("inventory_units", []),
                "restaurant_type": input_data.get("restaurant_type", ""),
            }, ensure_ascii=False)
        return system, user

    def _process_response(self, response: str) -> dict[str, Any]:
        data = self._parse_response(response)
        return {
            "issues":       data.get("issues", []),
            "suggestions":  data.get("suggestions", []),
            "looks_good":   data.get("looks_good", True),  # safe default — don't block on parse failure
            "raw_response": response,
        }
