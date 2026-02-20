"""
Readiness KPIs (subtask 2.7): onboarding completeness & standardization scorecard.

Phase A: readiness-only (no operational/performance KPIs). Produces a deterministic
JSON-serializable report from the in-memory model (registries + recipes + normalization).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from core.data_model import (
    CategoryRecipeRegistry,
    DEFAULT_INVENTORY_CATEGORIES,
    FamilyInventoryRegistry,
    Ingredient,
    InventoryItemRegistry,
    InventoryUnitEquivalenceRegistry,
    InventoryUnitRegistry,
    Recipe,
    RecipeUnitRegistry,
    Restaurant,
)
from core.data_model_utils import resolve_ingredient_to_inventory_item
from core.normalization import RecipeUnitConversionRegistry, normalize_recipe_for_deduction
from core.taxonomy import IngredientTaxonomy, InventoryTaxonomy, RecipeTaxonomy, Taxonomy


SCHEMA_VERSION = "1.0"

# Phase A dimension weights (locked)
DIMENSION_WEIGHTS: dict[str, float] = {
    "setup": 0.20,
    "recipes": 0.25,
    "inventory": 0.20,
    "normalization": 0.30,
    "taxonomy": 0.00,
}

# Targets for the two "truth" KPIs (locked)
TRUTH_TARGETS: dict[str, tuple[float, float]] = {
    "recipes.ingredientsLinkedToInventoryPct": (0.95, 0.80),
    "normalization.deductionCoveragePct": (0.90, 0.70),
}

# Default targets (Implementation decisions)
DEFAULT_REQUIRED_VALID_TARGETS = (1.0, 0.95)  # ok, warn
DEFAULT_COVERAGE_TARGETS = (0.90, 0.70)  # ok, warn

# Score bands (Implementation decisions)
OK_SCORE_MIN = 90.0
WARN_SCORE_MIN = 70.0


@dataclass(frozen=True)
class EvidenceRef:
    """Pointer to an example entity used as evidence for a KPI."""
    entity_type: str
    ref: str
    reason: str


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _grade_from_score(score_0_100: float) -> str:
    if score_0_100 >= 90:
        return "A"
    if score_0_100 >= 80:
        return "B"
    if score_0_100 >= 70:
        return "C"
    return "D"


def _status_from_score(score_0_100: float) -> str:
    if score_0_100 >= OK_SCORE_MIN:
        return "ok"
    if score_0_100 >= WARN_SCORE_MIN:
        return "warn"
    return "fail"


def _status_from_ratio(value: float, min_ok: float, min_warn: float) -> str:
    if value >= min_ok:
        return "ok"
    if value >= min_warn:
        return "warn"
    return "fail"


def _score_from_ratio(value: float, min_ok: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return _clamp(value / min_ok, 0.0, 1.0) * 100.0


def _status_from_count(count: int, required_min: int) -> str:
    return "ok" if count >= required_min else "fail"


def _score_from_count(count: int, required_min: int) -> float:
    return 100.0 if count >= required_min else 0.0


def _evidence_list(items: list[EvidenceRef], limit: int = 5) -> list[dict[str, str]]:
    return [asdict(x) for x in items[:limit]]


def _taxonomy_node_count(t: Taxonomy) -> int:
    # Taxonomy does not currently expose a public node count; use internal state.
    return len(getattr(t, "_nodes", set()))


def _ratio_kpi(
    *,
    kpi_id: str,
    dimension_id: str,
    title: str,
    description: str,
    numerator: int,
    denominator: int,
    min_ok: float,
    min_warn: float,
    evidence: Optional[list[EvidenceRef]] = None,
    remediation_summary: Optional[str] = None,
    remediation_actions: Optional[list[str]] = None,
    force_na: bool = False,
) -> dict[str, Any]:
    if force_na or denominator <= 0:
        return {
            "kpi_id": kpi_id,
            "dimension_id": dimension_id,
            "title": title,
            "description": description,
            "kind": "ratio",
            "value": None,
            "unit": "percent_0_1",
            "numerator": numerator,
            "denominator": denominator,
            "target": {"min_ok": min_ok, "min_warn": min_warn},
            "status": "na",
            "severity": "low",
            "evidence": {"sample_missing": _evidence_list(evidence or [])} if evidence else {},
            "remediation": (
                {"summary": remediation_summary, "next_actions": remediation_actions or []}
                if remediation_summary
                else {}
            ),
        }

    value = numerator / denominator
    status = _status_from_ratio(value, min_ok, min_warn)
    severity = "low"
    if kpi_id in TRUTH_TARGETS:
        severity = "high" if status == "fail" else ("medium" if status == "warn" else "low")
    return {
        "kpi_id": kpi_id,
        "dimension_id": dimension_id,
        "title": title,
        "description": description,
        "kind": "ratio",
        "value": value,
        "unit": "percent_0_1",
        "numerator": numerator,
        "denominator": denominator,
        "target": {"min_ok": min_ok, "min_warn": min_warn},
        "status": status,
        "severity": severity,
        "evidence": {"sample_missing": _evidence_list(evidence or [])} if evidence else {},
        "remediation": (
            {"summary": remediation_summary, "next_actions": remediation_actions or []}
            if remediation_summary
            else {}
        ),
    }


def _count_kpi(
    *,
    kpi_id: str,
    dimension_id: str,
    title: str,
    description: str,
    count: int,
    required_min: int = 1,
    evidence: Optional[list[EvidenceRef]] = None,
    remediation_summary: Optional[str] = None,
    remediation_actions: Optional[list[str]] = None,
) -> dict[str, Any]:
    status = _status_from_count(count, required_min)
    severity = "high" if status == "fail" else "low"
    return {
        "kpi_id": kpi_id,
        "dimension_id": dimension_id,
        "title": title,
        "description": description,
        "kind": "count",
        "value": count,
        "unit": "count",
        "target": {"required_min": required_min},
        "status": status,
        "severity": severity,
        "evidence": {"sample_missing": _evidence_list(evidence or [])} if evidence else {},
        "remediation": (
            {"summary": remediation_summary, "next_actions": remediation_actions or []}
            if remediation_summary
            else {}
        ),
    }


def _kpi_score_0_100(kpi: dict[str, Any]) -> Optional[float]:
    if kpi.get("status") == "na":
        return None
    kind = kpi.get("kind")
    if kind == "ratio":
        v = kpi.get("value")
        if v is None:
            return None
        return _score_from_ratio(float(v), float(kpi["target"]["min_ok"]))
    if kind == "count":
        return _score_from_count(int(kpi.get("value", 0)), int(kpi["target"].get("required_min", 1)))
    if kind == "boolean":
        return 100.0 if bool(kpi.get("value")) else 0.0
    if kind == "score":
        v = kpi.get("value")
        return float(v) if v is not None else None
    return None


def _dimension_score(kpis: list[dict[str, Any]]) -> tuple[Optional[float], str]:
    """Equal-weight average of non-na KPI scores, plus derived status (worst KPI status)."""
    scores: list[float] = []
    statuses: list[str] = []
    for k in kpis:
        if k.get("status") != "na":
            statuses.append(str(k.get("status")))
        s = _kpi_score_0_100(k)
        if s is not None:
            scores.append(s)
    if not scores:
        return (None, "na")
    avg = sum(scores) / len(scores)
    return (avg, _worst_status(statuses))


def _overall_score(dimensions: list[dict[str, Any]]) -> float:
    """Weighted average over non-na, non-zero-weight dimensions."""
    num = 0.0
    den = 0.0
    for d in dimensions:
        w = float(d.get("weight", 0.0))
        s = d.get("score_0_100")
        if w <= 0:
            continue
        if s is None:
            continue
        num += w * float(s)
        den += w
    if den <= 0:
        return 0.0
    return num / den


def _worst_status(statuses: list[str]) -> str:
    """Return worst among ok/warn/fail; defaults to ok if empty."""
    rank = {"ok": 0, "warn": 1, "fail": 2}
    if not statuses:
        return "ok"
    worst = max(statuses, key=lambda s: rank.get(s, 0))
    return worst if worst in rank else "ok"


def _valid_inventory_category_ids() -> set[int]:
    return {c.id for c in DEFAULT_INVENTORY_CATEGORIES}


def _normalize_name(s: str) -> str:
    return (s or "").strip().lower()


def compute_readiness_report(
    restaurant: Optional[Restaurant],
    *,
    recipes: list[Recipe],
    recipe_unit_registry: RecipeUnitRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    category_recipe_registry: CategoryRecipeRegistry,
    family_inventory_registry: FamilyInventoryRegistry,
    inventory_item_registry: InventoryItemRegistry,
    conversion_table: RecipeUnitConversionRegistry,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry] = None,
    ingredient_taxonomy: Optional[IngredientTaxonomy] = None,
    inventory_taxonomy: Optional[InventoryTaxonomy] = None,
    recipe_taxonomy: Optional[RecipeTaxonomy] = None,
) -> dict[str, Any]:
    """
    Compute the Phase A readiness report.

    Notes:
    - "Linked to inventory" is satisfied by inventory_item_id OR name-based lookup.
    - Enrichment-only KPIs are emitted as status=na in Phase A so they do not affect scores.
    """

    valid_recipe_unit_ids = recipe_unit_registry.valid_ids()
    valid_inventory_unit_ids = inventory_unit_registry.valid_ids()
    valid_category_ids = category_recipe_registry.valid_ids()
    valid_family_ids = family_inventory_registry.valid_ids()
    valid_item_category_ids = _valid_inventory_category_ids()

    # Collect recipes/ingredients
    all_ingredients: list[tuple[Recipe, Ingredient]] = []
    for r in recipes:
        for ing in r.ingredients:
            all_ingredients.append((r, ing))

    # --- Setup KPIs ---
    kpis_by_dim: dict[str, list[dict[str, Any]]] = {k: [] for k in DIMENSION_WEIGHTS.keys()}

    kpis_by_dim["setup"].append(
        _count_kpi(
            kpi_id="setup.recipeUnitsConfigured",
            dimension_id="setup",
            title="Recipe units configured",
            description="RecipeUnitRegistry has at least one unit.",
            count=len(valid_recipe_unit_ids),
        )
    )
    kpis_by_dim["setup"].append(
        _count_kpi(
            kpi_id="setup.inventoryUnitsConfigured",
            dimension_id="setup",
            title="Inventory units configured",
            description="InventoryUnitRegistry has at least one unit.",
            count=len(valid_inventory_unit_ids),
        )
    )
    kpis_by_dim["setup"].append(
        _count_kpi(
            kpi_id="setup.recipeCategoriesConfigured",
            dimension_id="setup",
            title="Recipe categories configured",
            description="CategoryRecipeRegistry has at least one category.",
            count=len(valid_category_ids),
        )
    )
    kpis_by_dim["setup"].append(
        _count_kpi(
            kpi_id="setup.inventoryFamiliesConfigured",
            dimension_id="setup",
            title="Inventory families configured",
            description="FamilyInventoryRegistry has at least one family.",
            count=len(valid_family_ids),
        )
    )
    items = inventory_item_registry.list_all()
    kpis_by_dim["setup"].append(
        _count_kpi(
            kpi_id="setup.inventoryItemsPresent",
            dimension_id="setup",
            title="Inventory items present",
            description="InventoryItemRegistry has at least one inventory item.",
            count=len(items),
        )
    )
    kpis_by_dim["setup"].append(
        _count_kpi(
            kpi_id="setup.recipesPresent",
            dimension_id="setup",
            title="Recipes present",
            description="At least one recipe exists.",
            count=len(recipes),
        )
    )

    # Registry hygiene ratios (mostly sanity checks; still computed)
    # Recipe units
    ru_missing: list[EvidenceRef] = []
    ru_ok = 0
    ru_all = 0
    for uid in sorted(valid_recipe_unit_ids):
        u = recipe_unit_registry.get(uid)
        if u is None:
            continue
        ru_all += 1
        if (u.name or "").strip() and (u.symbol or "").strip():
            ru_ok += 1
        else:
            ru_missing.append(EvidenceRef("recipe_unit", f"RecipeUnit#{uid}", "Missing name or symbol"))
    kpis_by_dim["setup"].append(
        _ratio_kpi(
            kpi_id="setup.recipeUnitsRequiredFieldsValidPct",
            dimension_id="setup",
            title="Recipe units required fields valid",
            description="Percent of recipe units with non-empty name and symbol.",
            numerator=ru_ok,
            denominator=ru_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=ru_missing,
        )
    )

    # Inventory units
    iu_missing: list[EvidenceRef] = []
    iu_ok = 0
    iu_all = 0
    for uid in sorted(valid_inventory_unit_ids):
        u = inventory_unit_registry.get(uid)
        if u is None:
            continue
        iu_all += 1
        ok = bool((u.name or "").strip() and (u.symbol or "").strip())
        if u.base_unit_id is not None:
            ok = ok and (inventory_unit_registry.get(u.base_unit_id) is not None)
            ok = ok and math.isfinite(u.factor_to_base) and u.factor_to_base > 0
        if ok:
            iu_ok += 1
        else:
            iu_missing.append(EvidenceRef("inventory_unit", f"InventoryUnit#{uid}", "Invalid required fields"))
    kpis_by_dim["setup"].append(
        _ratio_kpi(
            kpi_id="setup.inventoryUnitsRequiredFieldsValidPct",
            dimension_id="setup",
            title="Inventory units required fields valid",
            description="Percent of inventory units with non-empty name and symbol and valid base_unit chain when set.",
            numerator=iu_ok,
            denominator=iu_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=iu_missing,
        )
    )

    # Category recipes
    cr_missing: list[EvidenceRef] = []
    cr_ok = 0
    cr_all = 0
    for cid in sorted(valid_category_ids):
        c = category_recipe_registry.get(cid)
        if c is None:
            continue
        cr_all += 1
        if (c.name or "").strip():
            cr_ok += 1
        else:
            cr_missing.append(EvidenceRef("category", f"CategoryRecipe#{cid}", "Missing name"))
    kpis_by_dim["setup"].append(
        _ratio_kpi(
            kpi_id="setup.categoryRecipesRequiredFieldsValidPct",
            dimension_id="setup",
            title="Recipe categories required fields valid",
            description="Percent of recipe categories with non-empty name.",
            numerator=cr_ok,
            denominator=cr_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=cr_missing,
        )
    )

    # Families
    fam_missing: list[EvidenceRef] = []
    fam_ok = 0
    fam_all = 0
    for fid in sorted(valid_family_ids):
        f = family_inventory_registry.get(fid)
        if f is None:
            continue
        fam_all += 1
        ok = bool((f.name or "").strip())
        if ok:
            fam_ok += 1
        else:
            fam_missing.append(EvidenceRef("family", f"FamilyInventory#{fid}", "Missing name"))
    kpis_by_dim["setup"].append(
        _ratio_kpi(
            kpi_id="setup.familyInventoriesRequiredFieldsValidPct",
            dimension_id="setup",
            title="Inventory families required fields valid",
            description="Percent of inventory families with non-empty name.",
            numerator=fam_ok,
            denominator=fam_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=fam_missing,
        )
    )

    # --- Recipe KPIs ---
    kpis_by_dim["recipes"].append(
        _count_kpi(
            kpi_id="recipes.recipeCount",
            dimension_id="recipes",
            title="Recipe count",
            description="Number of recipes.",
            count=len(recipes),
        )
    )
    kpis_by_dim["recipes"].append(
        _count_kpi(
            kpi_id="recipes.ingredientCount",
            dimension_id="recipes",
            title="Ingredient count",
            description="Total number of ingredients across all recipes.",
            count=len(all_ingredients),
        )
    )

    # Ingredient recipe unit valid
    ing_unit_ok = 0
    ing_unit_all = len(all_ingredients)
    ing_unit_missing: list[EvidenceRef] = []
    for r, ing in all_ingredients:
        if ing.unit_id in valid_recipe_unit_ids:
            ing_unit_ok += 1
        else:
            ing_unit_missing.append(
                EvidenceRef(
                    "ingredient",
                    f"Recipe#{r.id}: {ing.name!r}",
                    f"unit_id {ing.unit_id} not in RecipeUnitRegistry",
                )
            )
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.ingredientRecipeUnitValidPct",
            dimension_id="recipes",
            title="Ingredients have valid recipe units",
            description="Percent of ingredients whose unit_id exists in RecipeUnitRegistry.",
            numerator=ing_unit_ok,
            denominator=ing_unit_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=ing_unit_missing,
            remediation_summary="Configure recipe units and update ingredients to use valid unit ids.",
            remediation_actions=[
                "Add missing RecipeUnits to RecipeUnitRegistry",
                "Update ingredients to reference valid unit_id",
            ],
        )
    )

    # Ingredients linked to inventory (truth KPI)
    linked_ok = 0
    linked_all = len(all_ingredients)
    linked_missing: list[EvidenceRef] = []
    for r, ing in all_ingredients:
        item = resolve_ingredient_to_inventory_item(ing, inventory_item_registry)
        if item is not None:
            linked_ok += 1
        else:
            linked_missing.append(
                EvidenceRef(
                    "ingredient",
                    f"Recipe#{r.id}: {ing.name!r}",
                    "No inventory item found by id or name",
                )
            )
    ok_target, warn_target = TRUTH_TARGETS["recipes.ingredientsLinkedToInventoryPct"]
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.ingredientsLinkedToInventoryPct",
            dimension_id="recipes",
            title="Ingredients linked to inventory",
            description="Percent of ingredients that can resolve to an InventoryItem (by inventory_item_id or by name).",
            numerator=linked_ok,
            denominator=linked_all,
            min_ok=ok_target,
            min_warn=warn_target,
            evidence=linked_missing,
            remediation_summary="Create or link inventory items for the missing ingredients.",
            remediation_actions=[
                "In onboarding: add missing inventory items",
                "Or set ingredient.inventory_item_id where the match is known",
            ],
        )
    )

    # Steps present
    steps_ok = 0
    steps_all = len(recipes)
    steps_missing: list[EvidenceRef] = []
    for r in recipes:
        if any((s or "").strip() for s in (r.steps or [])):
            steps_ok += 1
        else:
            steps_missing.append(EvidenceRef("recipe", f"Recipe#{r.id}: {r.name!r}", "Missing steps"))
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.stepsPresentPct",
            dimension_id="recipes",
            title="Recipes have steps",
            description="Percent of recipes with non-empty steps.",
            numerator=steps_ok,
            denominator=steps_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=steps_missing,
        )
    )

    # Recipe required fields valid (name, category_id exists, ingredients list)
    rec_ok = 0
    rec_all = len(recipes)
    rec_missing: list[EvidenceRef] = []
    for r in recipes:
        reasons: list[str] = []
        if not (r.name or "").strip():
            reasons.append("Missing name")
        if r.category_id not in valid_category_ids:
            reasons.append(f"category_id {r.category_id} not in CategoryRecipeRegistry")
        if r.ingredients is None:
            reasons.append("Missing ingredients list")
        if reasons:
            rec_missing.append(EvidenceRef("recipe", f"Recipe#{r.id}: {r.name!r}", "; ".join(reasons)))
        else:
            rec_ok += 1
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.recipesRequiredFieldsValidPct",
            dimension_id="recipes",
            title="Recipes required fields valid",
            description="Percent of recipes with valid required fields (name, category_id, ingredients).",
            numerator=rec_ok,
            denominator=rec_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=rec_missing,
        )
    )

    # Enrichment KPIs (Phase A: do not affect scoring)
    # recipesWithDescriptionPct
    desc_ok = sum(1 for r in recipes if (r.description or "").strip())
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.recipesWithDescriptionPct",
            dimension_id="recipes",
            title="Recipes with description",
            description="Percent of recipes with non-empty description (enrichment).",
            numerator=desc_ok,
            denominator=len(recipes),
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            force_na=True,
        )
    )
    # ingredientsRequiredFieldsValidPct
    ing_req_ok = 0
    ing_req_all = len(all_ingredients)
    ing_req_missing: list[EvidenceRef] = []
    for r, ing in all_ingredients:
        reasons: list[str] = []
        if not (ing.name or "").strip():
            reasons.append("Missing name")
        if not math.isfinite(ing.quantity) or ing.quantity <= 0:
            reasons.append("Invalid quantity (must be finite and > 0)")
        if ing.unit_id not in valid_recipe_unit_ids:
            reasons.append(f"unit_id {ing.unit_id} not in RecipeUnitRegistry")
        if reasons:
            ing_req_missing.append(EvidenceRef("ingredient", f"Recipe#{r.id}: {ing.name!r}", "; ".join(reasons)))
        else:
            ing_req_ok += 1
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.ingredientsRequiredFieldsValidPct",
            dimension_id="recipes",
            title="Ingredients required fields valid",
            description="Percent of ingredients with non-empty name, valid quantity, and unit_id in RecipeUnitRegistry.",
            numerator=ing_req_ok,
            denominator=ing_req_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=ing_req_missing,
        )
    )
    # ingredientsInventoryItemIdSetPct (enrichment)
    idset_ok = sum(1 for _, ing in all_ingredients if ing.inventory_item_id is not None)
    kpis_by_dim["recipes"].append(
        _ratio_kpi(
            kpi_id="recipes.ingredientsInventoryItemIdSetPct",
            dimension_id="recipes",
            title="Ingredients have inventory_item_id set",
            description="Percent of ingredients with inventory_item_id set (enrichment).",
            numerator=idset_ok,
            denominator=len(all_ingredients),
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            force_na=True,
        )
    )

    # --- Inventory KPIs ---
    # Basic validity ratios for inventory items
    inv_category_ok = 0
    inv_category_all = len(items)
    inv_category_missing: list[EvidenceRef] = []
    inv_unit_ok = 0
    inv_unit_missing: list[EvidenceRef] = []
    inv_family_ok = 0
    inv_family_all = 0
    inv_family_missing: list[EvidenceRef] = []
    inv_name_ok = 0
    inv_name_missing: list[EvidenceRef] = []
    inv_required_ok = 0
    inv_required_missing: list[EvidenceRef] = []

    for it in items:
        # category
        if it.category_id in valid_item_category_ids:
            inv_category_ok += 1
        else:
            inv_category_missing.append(
                EvidenceRef("inventory_item", f"InventoryItem#{it.id}: {it.name!r}", f"Invalid category_id {it.category_id}")
            )
        # unit
        if it.unit_id in valid_inventory_unit_ids:
            inv_unit_ok += 1
        else:
            inv_unit_missing.append(
                EvidenceRef("inventory_item", f"InventoryItem#{it.id}: {it.name!r}", f"unit_id {it.unit_id} not in InventoryUnitRegistry")
            )
        # family when set
        if it.family_id is not None:
            inv_family_all += 1
            if it.family_id in valid_family_ids:
                inv_family_ok += 1
            else:
                inv_family_missing.append(
                    EvidenceRef("inventory_item", f"InventoryItem#{it.id}: {it.name!r}", f"family_id {it.family_id} not in FamilyInventoryRegistry")
                )
        # name
        if (it.name or "").strip():
            inv_name_ok += 1
        else:
            inv_name_missing.append(
                EvidenceRef("inventory_item", f"InventoryItem#{it.id}", "Missing name")
            )
        # required fields valid
        reasons: list[str] = []
        if not (it.name or "").strip():
            reasons.append("Missing name")
        if it.category_id not in valid_item_category_ids:
            reasons.append(f"Invalid category_id {it.category_id}")
        if it.unit_id not in valid_inventory_unit_ids:
            reasons.append(f"unit_id {it.unit_id} not in InventoryUnitRegistry")
        if reasons:
            inv_required_missing.append(
                EvidenceRef("inventory_item", f"InventoryItem#{it.id}: {it.name!r}", "; ".join(reasons))
            )
        else:
            inv_required_ok += 1

    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.itemCategoryValidPct",
            dimension_id="inventory",
            title="Inventory items have valid category",
            description="Percent of inventory items whose category_id is in the fixed set (Perecedero/No perecedero).",
            numerator=inv_category_ok,
            denominator=inv_category_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=inv_category_missing,
        )
    )
    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.itemUnitValidPct",
            dimension_id="inventory",
            title="Inventory items have valid inventory units",
            description="Percent of inventory items whose unit_id exists in InventoryUnitRegistry.",
            numerator=inv_unit_ok,
            denominator=inv_category_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=inv_unit_missing,
        )
    )
    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.itemFamilyValidPctWhenSet",
            dimension_id="inventory",
            title="Inventory items have valid family when set",
            description="For items with family_id set, percent whose family_id exists in FamilyInventoryRegistry.",
            numerator=inv_family_ok,
            denominator=inv_family_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=inv_family_missing,
        )
    )
    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.nonEmptyNamesPct",
            dimension_id="inventory",
            title="Inventory items have non-empty names",
            description="Percent of inventory items with non-empty name.",
            numerator=inv_name_ok,
            denominator=inv_category_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=inv_name_missing,
        )
    )
    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.itemsRequiredFieldsValidPct",
            dimension_id="inventory",
            title="Inventory items required fields valid",
            description="Percent of inventory items with valid required fields (name, category_id, unit_id).",
            numerator=inv_required_ok,
            denominator=inv_category_all,
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            evidence=inv_required_missing,
        )
    )

    # Enrichment inventory KPIs (Phase A: do not affect scoring)
    fam_set = sum(1 for it in items if it.family_id is not None)
    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.itemsWithFamilyPct",
            dimension_id="inventory",
            title="Inventory items with family set",
            description="Percent of inventory items with family_id set (enrichment).",
            numerator=fam_set,
            denominator=len(items),
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            force_na=True,
        )
    )
    desc_set = sum(1 for it in items if (getattr(it, "description", None) or "").strip())
    kpis_by_dim["inventory"].append(
        _ratio_kpi(
            kpi_id="inventory.itemsWithDescriptionPct",
            dimension_id="inventory",
            title="Inventory items with description",
            description="Percent of inventory items with non-empty description (enrichment).",
            numerator=desc_set,
            denominator=len(items),
            min_ok=DEFAULT_REQUIRED_VALID_TARGETS[0],
            min_warn=DEFAULT_REQUIRED_VALID_TARGETS[1],
            force_na=True,
        )
    )

    # --- Normalization KPIs ---
    ok_target, warn_target = TRUTH_TARGETS["normalization.deductionCoveragePct"]
    denom_resolvable = 0
    num_deducted = 0
    skipped_evidence: list[EvidenceRef] = []

    # Compute per-ingredient so we can attach evidence deterministically.
    for r, ing in all_ingredients:
        item = resolve_ingredient_to_inventory_item(ing, inventory_item_registry)
        if item is None:
            continue
        denom_resolvable += 1

        # Attempt normalization for this single ingredient (for numerator)
        single = Recipe(
            r.id,
            r.name,
            r.category_id,
            r.description,
            r.steps,
            ingredients=[ing],
        )
        lines = normalize_recipe_for_deduction(
            single,
            family_inventory_registry,
            inventory_unit_registry,
            conversion_table,
            # normalize_recipe_for_deduction expects resolver returning (item_id, family_id, item_unit_id)
            # Use the already-agreed id-or-name resolution.
            lambda x: (item.id, item.family_id, item.unit_id),
            equivalence_registry=equivalence_registry,
        )
        if lines:
            num_deducted += 1
            continue

        # Evidence: classify likely reason using the same inputs and normalization rules.
        reason = _classify_normalization_skip_reason(
            ing=ing,
            item_id=item.id,
            family_id=item.family_id,
            item_unit_id=item.unit_id,
            family_registry=family_inventory_registry,
            unit_registry=inventory_unit_registry,
            conversion_table=conversion_table,
            equivalence_registry=equivalence_registry,
        )
        skipped_evidence.append(
            EvidenceRef("ingredient", f"Recipe#{r.id}: {ing.name!r}", reason)
        )

    kpis_by_dim["normalization"].append(
        _ratio_kpi(
            kpi_id="normalization.deductionCoveragePct",
            dimension_id="normalization",
            title="Deduction coverage",
            description="Of ingredients that resolve to inventory items, percent that produce a DeductionLine under normalize_recipe_for_deduction.",
            numerator=num_deducted,
            denominator=denom_resolvable,
            min_ok=ok_target,
            min_warn=warn_target,
            evidence=skipped_evidence,
            remediation_summary="Add missing conversions or fix unit configuration so more ingredients can be normalized for deduction.",
            remediation_actions=[
                "Ensure inventory units are configured and valid",
                "Add RecipeUnitConversionRegistry entries for ingredients with incompatible units",
                "Verify unit chains (base_unit_id) are correct and compatible",
            ],
        )
    )

    # Optional conversionTableCoveragePct (Phase A: emit as na to avoid overfitting)
    kpis_by_dim["normalization"].append(
        _ratio_kpi(
            kpi_id="normalization.conversionTableCoveragePct",
            dimension_id="normalization",
            title="Conversion table coverage (optional)",
            description="Percent of ingredients that require conversion table entries that have an entry (optional in Phase A).",
            numerator=0,
            denominator=0,
            min_ok=DEFAULT_COVERAGE_TARGETS[0],
            min_warn=DEFAULT_COVERAGE_TARGETS[1],
            force_na=True,
        )
    )

    # --- Taxonomy KPIs (Phase A: excluded from overall score) ---
    inv_tax_nodes = 0
    ing_tax_nodes = 0
    inv_tax_total = len(items)
    ing_tax_total = len({ _normalize_name(ing.name) for _, ing in all_ingredients if (ing.name or "").strip() })

    inv_tax_is_empty = True
    ing_tax_is_empty = True
    if inventory_taxonomy is not None:
        inv_tax_nodes = _taxonomy_node_count(inventory_taxonomy.taxonomy)
        inv_tax_is_empty = inv_tax_nodes == 0
    if ingredient_taxonomy is not None:
        ing_tax_nodes = _taxonomy_node_count(ingredient_taxonomy.taxonomy)
        ing_tax_is_empty = ing_tax_nodes == 0

    inv_in_tax = 0
    if inventory_taxonomy is not None and not inv_tax_is_empty:
        for it in items:
            if inventory_taxonomy.taxonomy.has_node(str(it.id)):
                inv_in_tax += 1
    kpis_by_dim["taxonomy"].append(
        _ratio_kpi(
            kpi_id="taxonomy.inventoryItemsInTaxonomyPct",
            dimension_id="taxonomy",
            title="Inventory items in taxonomy",
            description="Percent of inventory items whose id (as string) exists as a node in InventoryTaxonomy.",
            numerator=inv_in_tax,
            denominator=inv_tax_total,
            min_ok=DEFAULT_COVERAGE_TARGETS[0],
            min_warn=DEFAULT_COVERAGE_TARGETS[1],
            force_na=(inventory_taxonomy is None or inv_tax_is_empty),
        )
    )

    ing_in_tax = 0
    if ingredient_taxonomy is not None and not ing_tax_is_empty:
        for name in {_normalize_name(ing.name) for _, ing in all_ingredients if (ing.name or "").strip()}:
            if ingredient_taxonomy.taxonomy.has_node(name):
                ing_in_tax += 1
    kpis_by_dim["taxonomy"].append(
        _ratio_kpi(
            kpi_id="taxonomy.ingredientsInTaxonomyPct",
            dimension_id="taxonomy",
            title="Ingredients in taxonomy",
            description="Percent of unique ingredient names that exist as nodes in IngredientTaxonomy (node_id = normalized name).",
            numerator=ing_in_tax,
            denominator=ing_tax_total,
            min_ok=DEFAULT_COVERAGE_TARGETS[0],
            min_warn=DEFAULT_COVERAGE_TARGETS[1],
            force_na=(ingredient_taxonomy is None or ing_tax_is_empty),
        )
    )

    # --- Assemble dimension objects ---
    dimensions: list[dict[str, Any]] = []
    kpis_flat: list[dict[str, Any]] = []
    for dim_id, weight in DIMENSION_WEIGHTS.items():
        dim_kpis = kpis_by_dim.get(dim_id, [])
        score, status = _dimension_score(dim_kpis)
        dim_status = status if status != "na" else ("ok" if weight == 0 else "fail")
        dimensions.append(
            {
                "dimension_id": dim_id,
                "title": _dimension_title(dim_id),
                "weight": weight,
                "score_0_100": score,
                "status": dim_status,
                "kpi_ids": [k["kpi_id"] for k in dim_kpis],
            }
        )
        # Emit per-KPI weights (equal within dimension)
        # (Still useful for UI; scoring logic re-normalizes by excluding na.)
        per_weight = 1.0 / len(dim_kpis) if dim_kpis else 0.0
        for k in dim_kpis:
            k["weight"] = per_weight
            kpis_flat.append(k)

    overall_score = _overall_score(dimensions)
    overall_status = _worst_status(
        [
            str(d.get("status"))
            for d in dimensions
            if float(d.get("weight", 0.0)) > 0 and d.get("score_0_100") is not None
        ]
    )
    overall = {
        "score_0_100": overall_score,
        "grade": _grade_from_score(overall_score),
        "status": overall_status,
    }

    recommendations = _recommendations_from_kpis(kpis_flat)

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now_iso_z(),
        "restaurant": (
            {
                "restaurant_id": restaurant.id,
                "name": restaurant.name,
                "restaurant_type_id": restaurant.restaurant_type_id,
            }
            if restaurant is not None
            else None
        ),
        "overall": overall,
        "dimensions": dimensions,
        "kpis": kpis_flat,
        "recommendations": recommendations,
        "meta": {
            "counts": {
                "recipes": len(recipes),
                "ingredients": len(all_ingredients),
                "inventory_items": len(items),
            }
        },
    }

    # Keep schema stable: restaurant must be an object (or omitted) rather than None.
    if report["restaurant"] is None:
        report.pop("restaurant")
    return report


def _dimension_title(dimension_id: str) -> str:
    return {
        "setup": "Setup completeness",
        "recipes": "Recipe standardization",
        "inventory": "Inventory standardization",
        "normalization": "Normalization readiness",
        "taxonomy": "Taxonomy readiness",
    }.get(dimension_id, dimension_id)


def _classify_normalization_skip_reason(
    *,
    ing: Ingredient,
    item_id: int,
    family_id: Optional[int],
    item_unit_id: int,
    family_registry: FamilyInventoryRegistry,
    unit_registry: InventoryUnitRegistry,
    conversion_table: RecipeUnitConversionRegistry,
    equivalence_registry: Optional[InventoryUnitEquivalenceRegistry],
) -> str:
    if not math.isfinite(ing.quantity) or ing.quantity <= 0:
        return "Invalid quantity (must be finite and > 0)"
    if unit_registry.get(item_unit_id) is None:
        return f"Inventory unit_id {item_unit_id} for item {item_id} not in InventoryUnitRegistry"

    # If a conversion table entry exists, normalization may still skip if base_unit_id is invalid
    # or incompatible conversion fails.
    entry = conversion_table.get(ing.unit_id, family_id, ing.inventory_item_id)
    if entry is not None:
        if unit_registry.get(entry.base_unit_id) is None:
            return f"Conversion entry base_unit_id {entry.base_unit_id} not in InventoryUnitRegistry"
        # convert_quantity incompatibility surfaces as "skipped"; classify as unit incompatibility.
        if _root_base_unit_id_safe(entry.base_unit_id, unit_registry) != _root_base_unit_id_safe(item_unit_id, unit_registry):
            return "Conversion entry base unit incompatible with inventory item unit"
        return "Normalization failed unexpectedly despite conversion entry"

    # No entry: fallback path needs ing.unit_id present in inventory unit registry.
    if unit_registry.get(ing.unit_id) is None:
        return f"Ingredient unit_id {ing.unit_id} not in InventoryUnitRegistry"

    root_ing = _root_base_unit_id_safe(ing.unit_id, unit_registry)
    root_item = _root_base_unit_id_safe(item_unit_id, unit_registry)
    if root_ing is None or root_item is None:
        return "Unit chain error (broken chain or cycle)"
    if root_ing != root_item:
        return "Missing conversion entry (ingredient unit family differs from inventory item unit family)"

    # Same root but still skipped: likely broken chain or invalid equivalence.
    return "Unit conversion failed (broken chain or invalid equivalence)"


def _root_base_unit_id_safe(unit_id: int, registry: InventoryUnitRegistry) -> Optional[int]:
    visited: set[int] = set()
    current_id: Optional[int] = unit_id
    while current_id is not None:
        if current_id in visited:
            return None
        visited.add(current_id)
        u = registry.get(current_id)
        if u is None:
            return None
        if u.base_unit_id is None:
            return u.id
        current_id = u.base_unit_id
    return None


def _recommendations_from_kpis(kpis: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate actionable recommendations from warn/fail KPIs, sorted by impact."""
    recs: list[dict[str, Any]] = []

    def add_rec(
        *,
        recommendation_id: str,
        priority: str,
        title: str,
        why: str,
        related_kpi_ids: list[str],
        steps: list[str],
    ) -> None:
        recs.append(
            {
                "recommendation_id": recommendation_id,
                "priority": priority,
                "title": title,
                "why": why,
                "related_kpi_ids": related_kpi_ids,
                "steps": steps,
            }
        )

    by_id = {k["kpi_id"]: k for k in kpis}

    # Truth KPIs: highest leverage recommendations.
    link_kpi = by_id.get("recipes.ingredientsLinkedToInventoryPct")
    if link_kpi and link_kpi.get("status") in {"warn", "fail"}:
        add_rec(
            recommendation_id="rec.linkIngredientsToInventory",
            priority="high",
            title="Link recipe ingredients to inventory items",
            why="Without this, deduction and standardization reports skip ingredients.",
            related_kpi_ids=["recipes.ingredientsLinkedToInventoryPct"],
            steps=[
                "Open each recipe’s ingredient list",
                "For missing items: create InventoryItem (category + unit) and link",
                "Recompute readiness",
            ],
        )

    cov_kpi = by_id.get("normalization.deductionCoveragePct")
    if cov_kpi and cov_kpi.get("status") in {"warn", "fail"}:
        add_rec(
            recommendation_id="rec.increaseDeductionCoverage",
            priority="high",
            title="Increase deduction coverage (normalization)",
            why="If ingredients can’t be normalized, theoretical consumption reports will be incomplete.",
            related_kpi_ids=["normalization.deductionCoveragePct"],
            steps=[
                "Review skipped ingredient evidence in the readiness report",
                "Add conversion table entries for incompatible units (RecipeUnitConversionRegistry)",
                "Fix inventory unit chains (base_unit_id/factor_to_base) when broken",
                "Recompute readiness",
            ],
        )

    # Setup completeness: missing registries.
    for kpi_id, rec_id, title in (
        ("setup.recipeUnitsConfigured", "rec.configureRecipeUnits", "Configure recipe units"),
        ("setup.inventoryUnitsConfigured", "rec.configureInventoryUnits", "Configure inventory units"),
        ("setup.recipeCategoriesConfigured", "rec.configureCategories", "Configure recipe categories"),
        ("setup.inventoryFamiliesConfigured", "rec.configureFamilies", "Configure inventory families"),
        ("setup.inventoryItemsPresent", "rec.addInventoryItems", "Add inventory items"),
        ("setup.recipesPresent", "rec.addRecipes", "Add recipes"),
    ):
        k = by_id.get(kpi_id)
        if k and k.get("status") == "fail":
            add_rec(
                recommendation_id=rec_id,
                priority="high",
                title=title,
                why="This is required scaffolding for onboarding readiness.",
                related_kpi_ids=[kpi_id],
                steps=["Complete onboarding configuration for this section", "Recompute readiness"],
            )

    # Sort by a simple impact heuristic: high priority first, then by dimension weight if known.
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: (priority_rank.get(r["priority"], 9), r["recommendation_id"]))
    return recs[:10]

