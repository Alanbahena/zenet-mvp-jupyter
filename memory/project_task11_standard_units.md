---
name: Task 11 — Standard unit chain prerequisite
description: Task 11 must hardcode standard unit chains (kg→g, L→ml) in seed_data.py and data_model.py templates before deduction logic runs
type: project
---

Before implementing Estructura deduction logic in Task 11, the standard inventory unit chains must be hardcoded (not operator-collected):

- g  → root (base_unit_id=None, factor_to_base=1.0)
- kg → base_unit_id=g, factor_to_base=1000.0
- ml → root (base_unit_id=None, factor_to_base=1.0)
- L  → base_unit_id=ml, factor_to_base=1000.0
- pza → root (base_unit_id=None, factor_to_base=1.0)

These are universal physical facts — no operator input needed. Changes go in:
- scripts/seed_data.py (INVENTORY_UNITS list)
- core/domain/data_model.py (_INVENTORY_UNIT_TEMPLATES for all restaurant types)

Without this, convert_quantity and to_base_quantity cannot resolve cross-unit deductions (e.g. recipe says 250g, inventory item tracked in kg).

Operator-specific contextual units (caja, bolsa, bote) are NOT included here — those belong in Configuración (level 1) and Alineamiento/Estructura (level 2 per-item).
