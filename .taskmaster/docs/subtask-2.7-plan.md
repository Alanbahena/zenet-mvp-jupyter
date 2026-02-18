# Implementation plan: Subtask 2.7 — Readiness KPIs (onboarding completeness & standardization)

## Goal (Phase A: readiness-only)

After onboarding, the operator should immediately see **how complete and standardized** the restaurant setup is—without needing sales, purchases, or ongoing operations data.

This subtask defines:
- A **readiness-only KPI schema** (serializable JSON + optional Python dataclasses)
- A **computation plan** to generate a readiness report from the in-memory model (registries + recipes + normalization tables + optional taxonomy)
- A **scoring model** (0–100 overall + per-dimension breakdown)
- A **drilldown model** (what’s missing, where, and how to fix it)

This is intentionally not “performance KPIs” (no cost %, no waste %, no margin) because those require persistence + operational data (tasks 3+).

---

## Should this be part of subtask 2.5?

No.

- **Subtask 2.5** is “data model integration utilities” (format/validation/helpers/factories) and is already complete.
- Readiness KPIs are a **product-layer feature**: a standardized onboarding “scorecard” and exploration surface. It should be its own subtask (this one), **depending on 2.5** (because we’ll re-use resolvers/formatting/validation helpers).

---

## Inputs (what the KPI engine reads)

Minimum inputs to compute readiness:
- **Registries (2.2):**
  - `RecipeUnitRegistry`
  - `InventoryUnitRegistry`
  - `CategoryRecipeRegistry`
  - `FamilyInventoryRegistry`
  - `InventoryItemRegistry`
- **Data:**
  - `recipes: list[Recipe]`
- **Normalization (2.3):**
  - `RecipeUnitConversionRegistry` (conversion table)
  - Optional: `InventoryUnitEquivalenceRegistry` (item-specific equivalences)
- **Taxonomy (2.4):** optional
  - `IngredientTaxonomy`, `InventoryTaxonomy`, `RecipeTaxonomy` (or generic `Taxonomy`)

---

## Output: exact readiness-only KPI schema

### 1) Top-level report (JSON)

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-02-18T12:34:56Z",
  "restaurant": {
    "restaurant_id": 123,
    "name": "Mi Restaurante",
    "restaurant_type_id": 4
  },
  "overall": {
    "score_0_100": 78.5,
    "grade": "B",
    "status": "warn"
  },
  "dimensions": [
    {
      "dimension_id": "setup",
      "title": "Setup completeness",
      "weight": 0.20,
      "score_0_100": 90,
      "status": "ok",
      "kpi_ids": ["setup.recipeUnitsConfigured", "setup.inventoryUnitsConfigured"]
    }
  ],
  "kpis": [
    {
      "kpi_id": "recipes.ingredientsLinkedToInventoryPct",
      "dimension_id": "recipes",
      "title": "Ingredients linked to inventory",
      "description": "Percent of ingredients that can resolve to an InventoryItem (by inventory_item_id or by name).",
      "kind": "ratio",
      "value": 0.82,
      "unit": "percent_0_1",
      "numerator": 41,
      "denominator": 50,
      "target": { "min_ok": 0.95, "min_warn": 0.80 },
      "weight": 0.12,
      "status": "warn",
      "severity": "medium",
      "evidence": {
        "sample_missing": [
          { "entity_type": "ingredient", "ref": "Recipe#12: 'Sal'", "reason": "No inventory item found by id or name" }
        ]
      },
      "remediation": {
        "summary": "Create or link inventory items for the missing ingredients.",
        "next_actions": [
          "In onboarding: add missing inventory items",
          "Or set ingredient.inventory_item_id where the match is known"
        ]
      }
    }
  ],
  "recommendations": [
    {
      "recommendation_id": "rec.linkIngredientsToInventory",
      "priority": "high",
      "title": "Link recipe ingredients to inventory items",
      "why": "Without this, deduction and standardization reports skip ingredients.",
      "related_kpi_ids": ["recipes.ingredientsLinkedToInventoryPct"],
      "steps": [
        "Open each recipe’s ingredient list",
        "For missing items: create InventoryItem (category + unit) and link",
        "Recompute readiness"
      ]
    }
  ],
  "meta": {
    "counts": {
      "recipes": 12,
      "ingredients": 50,
      "inventory_items": 44
    }
  }
}
```

### 2) Enums / field constraints

- `overall.status`: `"ok" | "warn" | "fail"`
- `dimension.status`: `"ok" | "warn" | "fail"`
- `kpi.kind`: `"count" | "ratio" | "boolean" | "score"`
- `kpi.status`: `"ok" | "warn" | "fail" | "na"`
- `kpi.severity`: `"low" | "medium" | "high"`
- `unit` (suggested): `"count" | "percent_0_1" | "score_0_100" | "boolean"`

### 3) Evidence entity reference shape

```json
{
  "entity_type": "recipe | ingredient | inventory_item | recipe_unit | inventory_unit | family | category",
  "ref": "string",
  "reason": "string"
}
```

---

## Dimensions and KPIs (readiness-only set)

### Dimension A — Setup completeness (`setup`)

These are binary-ish “do we have the minimum scaffolding?” checks.

- `setup.recipeUnitsConfigured` (count): `RecipeUnitRegistry.valid_ids()` size > 0
- `setup.inventoryUnitsConfigured` (count): `InventoryUnitRegistry.valid_ids()` size > 0
- `setup.recipeCategoriesConfigured` (count): `CategoryRecipeRegistry.valid_ids()` size > 0
- `setup.inventoryFamiliesConfigured` (count): `FamilyInventoryRegistry.valid_ids()` size > 0
- `setup.inventoryItemsPresent` (count): `InventoryItemRegistry.list_all()` size > 0
- `setup.recipesPresent` (count): recipes count > 0

### Dimension B — Recipe standardization (`recipes`)

- `recipes.recipeCount` (count)
- `recipes.ingredientCount` (count)
- `recipes.ingredientRecipeUnitValidPct` (ratio): ingredient.unit_id is a valid RecipeUnit id
- `recipes.ingredientsLinkedToInventoryPct` (ratio): ingredient resolves to InventoryItem (id or name)
- `recipes.stepsPresentPct` (ratio): recipe.steps non-empty (basic standardization)

### Dimension C — Inventory standardization (`inventory`)

- `inventory.itemCategoryValidPct` (ratio): item.category_id is in fixed categories (Perecedero/No perecedero)
- `inventory.itemUnitValidPct` (ratio): item.unit_id exists in InventoryUnitRegistry
- `inventory.itemFamilyValidPctWhenSet` (ratio): for items with family_id not None, family_id exists in FamilyInventoryRegistry
- `inventory.nonEmptyNamesPct` (ratio): item.name non-empty (should be 1.0 if using registry)

### Dimension D — Normalization readiness (`normalization`)

Focus: can we produce “consumo teórico por platillo” (normalized deduction lines)?

- `normalization.deductionCoveragePct` (ratio):
  - denominator: ingredients that resolve to an InventoryItem
  - numerator: ingredients that produce a DeductionLine under `normalize_recipe_for_deduction`
  - evidence: sample skipped ingredients with reasons (missing unit, incompatible roots, missing conversion entry)

- `normalization.conversionTableCoveragePct` (ratio, optional):
  - denominator: ingredients that *require* conversion table (detected as “would be skipped for incompatible roots unless conversion exists”)
  - numerator: those that have a conversion entry in RecipeUnitConversionRegistry
  - note: exact detection can be done by attempting normalization and classifying skip reason (Phase A can infer from behavior rather than static analysis).

### Dimension E — Taxonomy readiness (`taxonomy`) (optional)

This is readiness for semantic exploration (manual discovery) after onboarding.

- `taxonomy.inventoryItemsInTaxonomyPct` (ratio): percent of inventory items whose id (as string) exists as a node in InventoryTaxonomy
- `taxonomy.ingredientsInTaxonomyPct` (ratio): percent of unique ingredient names that exist as nodes in IngredientTaxonomy (node_id = normalized name)

If taxonomies are empty/unpopulated, mark KPIs as `na` rather than failing the entire readiness score.

---

## Scoring model (Phase A)

1. Each KPI yields a status:
   - **ok** if `value >= min_ok`
   - **warn** if `min_warn <= value < min_ok`
   - **fail** if `value < min_warn`
   - **na** if KPI not applicable or data missing by design (e.g. taxonomy not used yet)

2. Convert KPI status/value to a **score_0_100**:
   - For ratios: `score = clamp(value / min_ok, 0, 1) * 100` (simple and interpretable)
   - For counts: `score = 100` if `count >= required_min` else `0` (or graded if we want)
   - For boolean: `100` or `0`

3. Dimension score = weighted average of KPI scores in that dimension.
4. Overall score = weighted average across dimensions (weights sum to 1.0).

Suggested default dimension weights:
- setup 0.20
- recipes 0.25
- inventory 0.20
- normalization 0.30
- taxonomy 0.05 (or 0.00 until taxonomy is used)

---

## Implementation plan (no code execution in this session)

### Step 2.7.1 — Create module + types

- New module: `core/readiness_kpis.py` (or `core/kpis_readiness.py`)
- Optional dataclasses:
  - `ReadinessReport`, `DimensionScore`, `KpiResult`, `Recommendation`, `EvidenceRef`
- Keep the output JSON identical to the schema above (dataclasses should serialize cleanly).

### Step 2.7.2 — Compute KPIs from current state

- Entry point:
  - `compute_readiness_report(restaurant: Restaurant | None, *, recipes: list[Recipe], registries..., conversion_table..., taxonomies... ) -> dict`
- Use `core.data_model_utils` helpers where possible:
  - `resolve_ingredient_to_inventory_item`
  - `make_resolver_from_item_registry`
  - `ingredients_to_display` (for evidence formatting)

### Step 2.7.3 — Normalization readiness computation

- For each recipe:
  - Build resolver from `InventoryItemRegistry`
  - Run `normalize_recipe_for_deduction(...)`
  - Compare produced lines vs resolvable ingredients
  - Collect “skipped ingredient evidence” (Phase A: infer reasons by checking resolution + unit existence; optionally re-run with try/except patterns)

### Step 2.7.4 — Recommendations (actionable next steps)

Generate recommendations from failing/warn KPIs. Example mapping:
- Low ingredientsLinkedToInventoryPct → “Link ingredients to inventory items”
- Low deductionCoveragePct → “Add conversion table entries” or “Fix unit registry/equivalences”
- Missing setup registries → “Complete configuration”

### Step 2.7.5 — Tests

- `tests/unit/test_readiness_kpis.py`
- Fixtures:
  - Minimal registries + 1 recipe + 1 ingredient fully linked → score high
  - Ingredient missing inventory item → issues + score down
  - Incompatible units without conversion table entry → coverage down

### Step 2.7.6 — Exports + docs

- Export `compute_readiness_report` (and types if desired) from `core/__init__.py`
- Add a short README snippet for “Readiness scorecard” (or leave for subtask 2.6)

---

## Checklist before marking 2.7 done

- [ ] Readiness KPI schema is documented (this file) and matches implementation output
- [ ] compute_readiness_report returns valid JSON for empty/minimal inputs
- [ ] KPIs include drilldowns/evidence for missing/invalid entities
- [ ] Overall score + dimension scores computed deterministically
- [ ] Unit tests cover at least 3 scenarios (good, partial, broken normalization)
- [ ] No dependency on persistence or operational data

