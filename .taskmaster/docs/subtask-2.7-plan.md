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

#### Registry entity completeness (required vs enrichment)

Even though registries validate on `add()`, it’s still useful to surface basic “configuration hygiene” KPIs:

- `setup.recipeUnitsRequiredFieldsValidPct` (ratio): % of RecipeUnits in RecipeUnitRegistry where:
  - `name` is non-empty
  - `symbol` is non-empty
  - (duplicates are already blocked by registry; this is primarily a sanity check / evidence generator)

- `setup.inventoryUnitsRequiredFieldsValidPct` (ratio): % of InventoryUnits in InventoryUnitRegistry where:
  - `name` is non-empty
  - `symbol` is non-empty
  - if `base_unit_id` is set, it exists in registry and `factor_to_base` is finite and > 0 (cycle prevention already enforced)

- `setup.categoryRecipesRequiredFieldsValidPct` (ratio): % of CategoryRecipe entries in CategoryRecipeRegistry where:
  - `name` is non-empty

- `setup.familyInventoriesRequiredFieldsValidPct` (ratio): % of FamilyInventory entries in FamilyInventoryRegistry where:
  - `name` is non-empty
  - optional enrichment: `base_unit_id` is set and valid (more relevant to reporting than deduction)

Note: **InventoryCategory** (Perecedero/No perecedero) is a fixed set (`DEFAULT_INVENTORY_CATEGORIES`), so we don’t score its “completeness”; we only score whether items reference valid category ids.

### Dimension B — Recipe standardization (`recipes`)

- `recipes.recipeCount` (count)
- `recipes.ingredientCount` (count)
- `recipes.ingredientRecipeUnitValidPct` (ratio): ingredient.unit_id is a valid RecipeUnit id
- `recipes.ingredientsLinkedToInventoryPct` (ratio): ingredient resolves to InventoryItem (id or name)
- `recipes.stepsPresentPct` (ratio): recipe.steps non-empty (basic standardization)

#### Recipe completeness KPIs (required vs enrichment)

In `core/data_model.py`, `Recipe` has required fields: `id`, `name`, `description`, `steps`, `category_id`, `ingredients`. For readiness, we should score **validity of required fields** and treat “richness” separately.

- `recipes.recipesRequiredFieldsValidPct` (ratio): % of recipes where:
  - `name` is non-empty
  - `category_id` exists in CategoryRecipeRegistry
  - `ingredients` list exists (always true if constructed normally; include mainly for evidence)
  - (do **not** require `id != 0` in Phase A)
  - evidence: sample invalid recipes with missing/invalid required fields

- `recipes.recipesWithDescriptionPct` (ratio, enrichment): % where `description` is non-empty
  - informational / low weight in Phase A

- `recipes.recipesWithStepsPct` (ratio, enrichment): % where `steps` has at least 1 non-empty step
  - this can either reuse `recipes.stepsPresentPct` or replace it (keep one KPI to avoid redundancy)

#### Ingredient completeness KPIs (required vs enrichment)

In `core/data_model.py`, `Ingredient` required fields: `name`, `quantity`, `unit_id` (and optional `inventory_item_id`).

- `recipes.ingredientsRequiredFieldsValidPct` (ratio): % of ingredients where:
  - `name` is non-empty
  - `quantity` is finite and > 0
  - `unit_id` exists in RecipeUnitRegistry
  - evidence: sample invalid ingredients with reasons

- `recipes.ingredientsInventoryItemIdSetPct` (ratio, enrichment): % of ingredients with `inventory_item_id is not None`
  - keep **separate** from `recipes.ingredientsLinkedToInventoryPct` (which is readiness-critical) because:
    - An ingredient can be linkable by **name match** even without an id set (still “ready”)
    - Setting `inventory_item_id` improves robustness (enrichment)

### Dimension C — Inventory standardization (`inventory`)

- `inventory.itemCategoryValidPct` (ratio): item.category_id is in fixed categories (Perecedero/No perecedero)
- `inventory.itemUnitValidPct` (ratio): item.unit_id exists in InventoryUnitRegistry
- `inventory.itemFamilyValidPctWhenSet` (ratio): for items with family_id not None, family_id exists in FamilyInventoryRegistry
- `inventory.nonEmptyNamesPct` (ratio): item.name non-empty (should be 1.0 if using registry)

#### Inventory completeness KPIs (required vs enrichment)

We **should** measure whether `InventoryItem` instances have their **required** properties valid, but we should **not** penalize missing *optional* properties as “not ready”.

In `core/data_model.py`, `InventoryItem` has:
- **Required (readiness-critical):** `name`, `unit_id`, `category_id` (and `id`, but id may be `0` before persistence)
- **Optional (enrichment):** `family_id`, `description`

Add these KPIs:

- `inventory.itemsRequiredFieldsValidPct` (ratio): % of inventory items where:
  - `name` is non-empty (strip)
  - `category_id` is one of the fixed InventoryCategory ids (Perecedero/No perecedero)
  - `unit_id` exists in `InventoryUnitRegistry`
  - (do **not** require `id != 0` in Phase A)
  - evidence: sample invalid items with which required field failed

- `inventory.itemsWithFamilyPct` (ratio, enrichment): % of inventory items where `family_id is not None`
  - status: typically `na` or low-weight in Phase A (unless you decide families are required during onboarding)

- `inventory.itemsWithDescriptionPct` (ratio, enrichment): % of inventory items where `description` is non-empty
  - status: informational (`na`/low weight) in Phase A

This gives the operator a clean split between **standardization readiness** (required fields) and **data richness** (optional fields that improve UX/search/reporting).

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

---

## Phase A defaults (locked)

These rules keep the readiness score trustworthy and consistent. Implement and test against them.

### Dimension weights (Phase A)

- setup: **0.20**
- recipes: **0.25**
- inventory: **0.20**
- normalization: **0.30**
- taxonomy: **0.00** (agreed: excluded until taxonomies are actively populated)

Weights sum to 1.0. Taxonomy dimension can still appear in the report with status `na`; it must not affect the overall score.

### NA handling

- **KPI with status `na`:** Excluded from that dimension’s score (do not count in weighted average for the dimension).
- **Dimension with all KPIs `na` or weight 0:** Excluded from overall score (taxonomy in Phase A).
- So overall = weighted average of setup, recipes, inventory, normalization only.

### Targets for the two “truth” KPIs

If these aren’t set, users will argue with the score. Lock these defaults:

- **`recipes.ingredientsLinkedToInventoryPct`**
  - ok: **≥ 0.95**
  - warn: **≥ 0.80**
  - fail: **< 0.80**

- **`normalization.deductionCoveragePct`**
  - ok: **≥ 0.90**
  - warn: **≥ 0.70**
  - fail: **< 0.70**

(Tune later if needed; document any override in this section.)

### Name-based linking (Phase A behavior)

- **Readiness-critical:** “Linked to inventory” = ingredient resolves to an InventoryItem by **inventory_item_id OR by name** (get_by_name). So name-based linking counts as linked.
- **Enrichment:** `recipes.ingredientsInventoryItemIdSetPct` = % of ingredients with `inventory_item_id` set. Setting ids is more robust (no name drift) but not required for Phase A readiness.
- **Report copy:** Be explicit in the readiness report (or UI) that name-linking is “acceptable but less robust” so users understand why the enrichment KPI exists. See `.taskmaster/docs/readiness-scorecard-ux.md` for presentation.

---

## Implementation decisions (for 2.7 implementation)

These choices remove ambiguity so the report is deterministic and UI-ready.

- **Grade (overall):** Map `score_0_100` to letter: A ≥ 90, B ≥ 80, C ≥ 70, D < 70. Use same bands for labels if needed (e.g. "Ready" ≥ 80, "Needs work" ≥ 60, "Not ready" < 60).
- **Overall status (ok/warn/fail):** Set from overall score: ok ≥ 90, warn ≥ 70, fail < 70 (or derive from worst dimension status; either is fine if consistent).
- **Dimension status:** Set from dimension score: ok ≥ 90, warn ≥ 70, fail < 70 (exclude `na` KPIs from dimension score as in NA handling).
- **Per-KPI weights inside a dimension:** Use **equal weight** for all non-`na` KPIs in that dimension (simplest). If a KPI is `na`, exclude it and re-normalize the rest.
- **Count-type KPIs (setup.*Configured, setup.*Present):** Treat as pass/fail: `required_min = 1` (score 100 if count ≥ 1, else 0). No need for higher thresholds in Phase A.
- **Default targets for other KPIs:** For any ratio KPI not explicitly set above, use: **min_ok = 1.0, min_warn = 0.95** for "required fields valid" / "configured" style; **min_ok = 0.9, min_warn = 0.7** for coverage-style ratios (or document overrides in "Phase A defaults" if you tune later).
- **Recommendations order:** Sort by impact (e.g. dimension weight × severity), then take top N (e.g. 3 for UI). Tie to related_kpi_ids as in schema.

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

