---
name: Task 11 — Estructura section vision
description: Operator-defined vision for Task 11: inventory structuring via chat + file upload, building on the base inventory from Alineamiento
type: project
---

## What Task 11 is (corrected scope)

Task 11 is NOT recipe structuring. Recipes were handled in Task 10 (Alineamiento).
Task 11 is **inventory structuring** — taking the base inventory generated in Alineamiento and enriching it with full structured data.

## Foundation

The base inventory from Alineamiento (Task 10) already exists and serves as the starting point. Task 11 builds on top of it.

## Process flow

1. Display the base inventory to the operator so they can see what already exists (split by the 2 inventory categories: Perecederos and No perecederos).
2. Chat interface where the agent guides the operator through structuring their inventory data. Agent asks if the operator has files to upload (e.g. supplier lists, inventory sheets), or if they prefer to provide it verbally/in writing.
3. Operator uploads files or provides data via chat.
4. Agent processes the data, reasons over it, and proposes a structured inventory based on the existing foundation. Agent asks follow-up questions as needed to fill in missing fields.

## Data fields per inventory item

- Nombre (name)
- Unidad de inventario (inventory unit / unit of measure)
- Categoría (Perecedero / No perecedero)
- Familia (inventory family)
- Descripción
- Unidad (unit name)
- Símbolo de unidad (unit symbol)
- Equivalencia (unit equivalence, only for non-standard units)

## Key rules

- **Equivalence is only required for non-standard units.** If the operator's inventory unit is non-standard, the agent must first ask whether the operator already knows the equivalence for that specific product. If they don't know, the agent proposes one; operator must confirm.
- **"Pieza" (pza) is treated as a standard unit** in this phase. No equivalence required for items measured in pza.
- Standard units in this phase: g, kg, ml, L, pza.
