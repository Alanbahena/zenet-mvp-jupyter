# InventoryItem, InventoryUnit, and InventoryUnitEquivalence — Relationship and Persistence

This document clarifies how **InventoryItem**, **InventoryUnit**, and **InventoryUnitEquivalence** relate and how they are persisted. It answers: *Does InventoryItem.unit_id point to InventoryUnit or to InventoryUnitEquivalence?*

**Context:** Task 3 (data persistence layer). Dict shapes are defined in [3.1/serialization-contract.md](3.1/serialization-contract.md).

---

## 1. Short answer

- **InventoryItem.unit_id** always references an **InventoryUnit** (by id).
- **InventoryUnitEquivalence** is a **separate entity** used when the unit is non-standard: it stores the **per-item conversion** to a base unit.
- The dict shape of InventoryItem does **not** change: `unit_id` is always an FK to InventoryUnit.

---

## 2. Roles of each entity

### 2.1 InventoryUnit

- Defines a unit of measure (e.g. kg, L, pza, caja, bolsa).
- Can be **standard** (`is_standard: true`) — e.g. kg, g, L, ml, pza — or **non-standard** (`is_standard: false`) — e.g. caja, bolsa, bote.
- May have global conversion: `base_unit_id` and `factor_to_base` (e.g. “1 caja = 10 kg” in general).
- **Persisted** as entity type `"inventory_unit"`.

### 2.2 InventoryItem

- One inventory product (e.g. “Leche entera”, “Fresas en caja”).
- **unit_id** → **always** references **InventoryUnit.id** (the unit in which this item is measured: kg, L, caja, etc.).
- Does **not** reference InventoryUnitEquivalence directly.
- **Persisted** as entity type `"inventory_item"`.

### 2.3 InventoryUnitEquivalence

- Provides **per-item** conversion when the item uses a **non-standard** unit.
- Key: `(unit_id, inventory_item_id)`.
- Meaning: “For *this* inventory item, when measured in *this* unit, 1 unit = `factor_to_base` in `base_unit_id`.”
- **Persisted** as entity type `"inventory_unit_equivalence"`.
- **Optional:** Only present when the item’s unit is non-standard and we need an item-specific conversion (e.g. “1 caja of strawberries = 2.5 kg”).

---

## 3. How they work together

### Standard unit (e.g. kg, L)

- InventoryItem has `unit_id` → InventoryUnit id for “kg”.
- That unit is standard; no item-specific conversion needed.
- **No** InventoryUnitEquivalence row for this item/unit.

### Non-standard unit (e.g. caja)

- InventoryItem has `unit_id` → InventoryUnit id for “caja”.
- To convert “cajas” to a base unit (e.g. kg), we need a factor **per item** (one caja of strawberries ≠ one caja of tomatoes).
- An **InventoryUnitEquivalence** row exists: `(unit_id=caja, inventory_item_id=strawberries_id)` → `base_unit_id=kg`, `factor_to_base=2.5`.
- At runtime: use InventoryItem + its unit_id; if the unit is non-standard, look up InventoryUnitEquivalence by `(unit_id, inventory_item_id)` to get the conversion.

So:

- **unit_id** on InventoryItem → always **InventoryUnit** (which unit we use for this item).
- **InventoryUnitEquivalence** → optional extra table/entity that says “for this (unit, item), here is the conversion to base.”

---

## 4. Example (persisted dicts)

**InventoryUnit (caja, non-standard):**

```json
{
  "id": 10,
  "name": "caja",
  "symbol": "caja",
  "description": "Caja estándar",
  "base_unit_id": null,
  "factor_to_base": 1.0,
  "is_standard": false
}
```

**InventoryItem (strawberries, measured in cajas):**

```json
{
  "id": 15,
  "name": "Fresas",
  "unit_id": 10,
  "category_id": 1,
  "family_id": 5,
  "description": "Fresas frescas en caja"
}
```

**InventoryUnitEquivalence (this box of strawberries = 2.5 kg):**

```json
{
  "unit_id": 10,
  "inventory_item_id": 15,
  "base_unit_id": 1,
  "factor_to_base": 2.5
}
```

Interpretation:

- Item 15 is measured in unit 10 (caja).
- For item 15, 1 caja = 2.5 kg (base_unit_id 1 = kg).

---

## 5. Summary table

| Question | Answer |
|----------|--------|
| What does InventoryItem.unit_id reference? | **InventoryUnit** (always). |
| Does unit_id ever reference InventoryUnitEquivalence? | **No.** |
| When is InventoryUnitEquivalence used? | When the item’s unit is non-standard and we need a per-item conversion factor. |
| Do we need a different dict shape for InventoryItem when the unit is non-standard? | **No.** Same shape: `unit_id` is always FK to InventoryUnit. |
| Where are the dict shapes defined? | [3.1/serialization-contract.md](3.1/serialization-contract.md) — no change needed. |

---

## 6. Implementation notes (for 3.3, 3.4, 3.5)

- **Serialization (3.3):** InventoryItem to_dict/from_dict use `unit_id` as FK to InventoryUnit only. No special handling for “equivalence” in the InventoryItem dict.
- **SQLite (3.4):** `inventory_item.unit_id` → FK to `inventory_unit(id)`. InventoryUnitEquivalence is a separate table with composite key `(unit_id, inventory_item_id)`.
- **Load order:** Load InventoryUnit and InventoryItem first; then load InventoryUnitEquivalence (it references both). When rebuilding InventoryUnitEquivalenceRegistry, register after both units and items are loaded.

---

**End of document.**
