import re

import gradio as gr

from gradio_app.session import stable_entity_id
from core import (
    RecipeUnitRegistry,
    InventoryUnitRegistry,
    CategoryRecipeRegistry,
    FamilyInventoryRegistry,
    InventoryItemRegistry,
    validate_recipe_for_deduction,
)
from core.domain.serialization import (
    restaurant_from_dict,
    recipe_from_dict,
    inventory_item_from_dict,
    recipe_unit_from_dict,
    inventory_unit_from_dict,
    category_recipe_from_dict,
    family_inventory_from_dict,
    recipe_unit_conversion_from_dict,
)
from core.operations.normalization import RecipeUnitConversionRegistry
from core.operations.readiness_kpis import compute_readiness_report

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

_SKIP_DIMENSIONS = {"taxonomy"}  # weight=0, always na — omit from progress bars

_HIDDEN_KPI_IDS = {
    "recipes.stepsPresentPct",
    "recipes.ingredientsInventoryItemIdSetPct",
    "inventory.itemsWithFamilyPct",
    "inventory.itemsWithDescriptionPct",
}

_UNIT_MISMATCH_REASON = (
    "Missing conversion entry "
    "(ingredient unit family differs from inventory item unit family)"
)


# ---------------------------------------------------------------------------
# Private helpers — unit mismatch resolution
# ---------------------------------------------------------------------------

def _parse_ingredient_name_from_ref(ref: str) -> str:
    """Extract ingredient name from EvidenceRef.ref string like "Recipe#1: 'tortillas'".

    ref format: "Recipe#N: 'ingredient_name'" (ingredient name via repr()).
    Falls back to the full ref string if the pattern does not match.
    Known limitation: ingredient names containing a single quote will not parse correctly.
    """
    m = re.search(r":\s*'(.+)'$", ref)
    return m.group(1) if m else ref


def _resolve_mismatch_units(
    ing_name: str,
    recipes: list,
    recipe_unit_registry: RecipeUnitRegistry,
    item_registry: InventoryItemRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
) -> tuple[str | None, str | None]:
    """Return (recipe_unit_symbol, inventory_unit_symbol) for a unit mismatch ingredient.

    Searches all recipes for the first ingredient matching ing_name, then resolves
    the recipe unit symbol and inventory item stock unit symbol.
    Returns (None, None) if the ingredient or its linked inventory item cannot be found.
    """
    for recipe in recipes:
        for ing in recipe.ingredients:
            if ing.name == ing_name:
                recipe_unit = recipe_unit_registry.get(ing.unit_id)
                linked_item = (
                    item_registry.get(ing.inventory_item_id)
                    if ing.inventory_item_id
                    else item_registry.get_by_name(ing.name)
                )
                if recipe_unit and linked_item:
                    inv_unit = inventory_unit_registry.get(linked_item.stock_unit_id)
                    return recipe_unit.symbol, (inv_unit.symbol if inv_unit else None)
    return None, None


# ---------------------------------------------------------------------------
# Private helpers — Resumen tab
# ---------------------------------------------------------------------------

def _build_resumen_md(
    report: dict,
    recipe_unit_registry: RecipeUnitRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    item_registry: InventoryItemRegistry,
    *,
    recipes: list,
    items: list,
) -> str:
    """Build the Resumen tab Markdown from a compute_readiness_report() output.

    Pure function — no DataLake access. Returns a non-empty string even when
    all KPIs are na (empty registries / no data).
    """
    lines = []

    # a) Header and overall score
    overall = report.get("overall", {})
    score = overall.get("score_0_100") or 0
    grade = overall.get("grade", "N/D")
    lines.append("## Tu restaurante está estandarizado")
    lines.append(f"**Puntuación general: {score:.0f} / 100 — Calificación: {grade}**")
    lines.append("")

    # b) Per-dimension progress bars
    _STATUS_ICON = {"ok": "✓", "warn": "⚠", "fail": "✗"}
    for dim in report.get("dimensions", []):
        if dim.get("dimension_id") in _SKIP_DIMENSIONS:
            continue
        dim_score = dim.get("score_0_100") or 0
        status = dim.get("status", "na")
        title = dim.get("title", dim.get("dimension_id", ""))
        filled = round(dim_score / 5)  # 0–20 blocks
        bar = "█" * filled + "░" * (20 - filled)
        icon = _STATUS_ICON.get(status, "-")
        lines.append(f"`{title}`  {bar}  {dim_score:.0f}%  {icon}")
    lines.append("")

    # c) Deduction coverage line
    ded_kpi = next(
        (k for k in report.get("kpis", [])
         if k.get("kpi_id") == "normalization.deductionCoveragePct"),
        None,
    )
    if ded_kpi and ded_kpi.get("status") != "na":
        numerator = ded_kpi.get("numerator", 0)
        denominator = ded_kpi.get("denominator", 0)
        lines.append(f"**Cobertura de deducción:** {numerator} de {denominator} ingredientes listos")
        lines.append("")

    # d) Logros completados
    logros = []
    logros.append("✓ Restaurante registrado")
    logros.append("✓ Nivel de estandarización definido")
    n_ru = len(recipe_unit_registry.valid_ids())
    if n_ru > 0:
        logros.append(f"✓ {n_ru} unidades de receta configuradas")
    n_fam = len({it.family_id for it in items if it.family_id})
    if n_fam > 0:
        logros.append(f"✓ {n_fam} familias de inventario configuradas")
    if len(recipes) > 0:
        logros.append(f"✓ {len(recipes)} recetas capturadas")
    if len(items) > 0:
        logros.append(f"✓ {len(items)} artículos de inventario estructurados")

    lines.append("**Logros completados:**")
    for logro in logros:
        lines.append(f"- {logro}")
    lines.append("")

    # e) Áreas de oportunidad — generic (top 3 fail/warn, hidden KPIs excluded)
    fail_warn = [
        k for k in report.get("kpis", [])
        if k.get("status") in ("fail", "warn")
        and k.get("kpi_id") not in _HIDDEN_KPI_IDS
    ]
    fail_warn.sort(key=lambda k: (
        0 if k["status"] == "fail" else 1,
        0 if k.get("severity") == "high" else 1,
    ))

    areas_lines = []
    for kpi in fail_warn[:3]:
        icon = "✗" if kpi["status"] == "fail" else "⚠"
        evidence_items = kpi.get("evidence", {}).get("sample_missing", [])
        generic_evs = [ev for ev in evidence_items if ev.get("reason") != _UNIT_MISMATCH_REASON]
        areas_lines.append(f"{icon} **{kpi['title']}**")
        for ev in generic_evs[:3]:
            areas_lines.append(f"  - {ev['ref']}")

    # f) Unit mismatch block — collected across ALL fail/warn KPIs
    all_mismatch_evs = []
    for kpi in report.get("kpis", []):
        if kpi.get("status") not in ("fail", "warn"):
            continue
        for ev in kpi.get("evidence", {}).get("sample_missing", []):
            if ev.get("reason") == _UNIT_MISMATCH_REASON:
                all_mismatch_evs.append(ev)

    if all_mismatch_evs:
        areas_lines.append("✗ **Ingredientes sin conversión de unidades definida:**")
        for ev in all_mismatch_evs[:5]:
            ing_name = _parse_ingredient_name_from_ref(ev["ref"])
            recipe_unit_sym, inv_unit_sym = _resolve_mismatch_units(
                ing_name, recipes, recipe_unit_registry, item_registry, inventory_unit_registry
            )
            if recipe_unit_sym and inv_unit_sym:
                areas_lines.append(
                    f"  → {ing_name}: receta usa \"{recipe_unit_sym}\","
                    f" inventario usa \"{inv_unit_sym}\""
                )
            else:
                areas_lines.append(f"  → {ev['ref']}")
        areas_lines.append("  *(Define la equivalencia para que Zenet pueda calcular el consumo)*")

    if areas_lines:
        lines.append("**Áreas de oportunidad:**")
        lines.extend(areas_lines)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers — Mi Restaurante / Recetas / Inventario tabs
# ---------------------------------------------------------------------------

def _build_mi_restaurante_md(
    restaurant,
    user_data: dict,
    classification_data: dict,
    *,
    recipe_units: list,
    inventory_units: list,
    categories: list,
    families: list,
    recipes: list,
    items: list,
) -> str:
    """Build the Mi Restaurante tab Markdown from loaded entities.

    Pure function — no DataLake access.
    """
    lines = []

    lines.append(f"## {restaurant.name}")
    operator = user_data.get("name", "—")
    std_level = classification_data.get("standardization_level", "N/D")
    lines.append(
        f"**Tipo:** {restaurant.restaurant_type_id}  |  "
        f"**Operador:** {operator}  |  "
        f"**Nivel de estandarización:** {std_level}"
    )

    description = classification_data.get("restaurant_description", "")
    if description:
        lines.append(f"_{description}_")

    lines.append("")
    lines.append("**Configuración:**")
    lines.append(f"- Unidades de receta: {len(recipe_units)}")
    lines.append(f"- Unidades de inventario: {len(inventory_units)}")
    lines.append(f"- Categorías de receta: {len(categories)}")
    lines.append(f"- Familias de inventario: {len(families)}")
    lines.append(f"- Artículos de inventario: {len(items)}")
    lines.append(f"- Recetas: {len(recipes)}")

    return "\n".join(lines)


def _build_recetas_md(
    recipes: list,
    recipe_unit_registry: RecipeUnitRegistry,
    item_registry: InventoryItemRegistry,
    category_registry: CategoryRecipeRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    conversion_table,
    family_registry: FamilyInventoryRegistry,
) -> str:
    """Build the Recetas tab Markdown from loaded recipes and registries.

    Pure function — no DataLake access. Badge determined by validate_recipe_for_deduction.
    """
    if not recipes:
        return "_(Sin recetas capturadas)_"

    lines = []
    for recipe in recipes:
        issues = validate_recipe_for_deduction(
            recipe, item_registry, inventory_unit_registry, conversion_table, family_registry
        )
        badge = "✓ Lista para deducción" if not issues else "⚠ Incompleta"

        cat = category_registry.get(recipe.category_id) if recipe.category_id is not None else None
        cat_name = cat.name if cat else "—"

        lines.append(f"### {recipe.name}  —  {badge}")
        lines.append(f"Categoría: {cat_name}")
        lines.append("")
        lines.append("**Ingredientes:**")
        for ing in recipe.ingredients:
            unit = recipe_unit_registry.get(ing.unit_id)
            unit_sym = unit.symbol if unit else str(ing.unit_id)
            linked = ing.inventory_item_id is not None or item_registry.get_by_name(ing.name) is not None
            link_label = "✓ vinculado" if linked else "⚠ sin vincular"
            lines.append(f"  - {ing.name}: {ing.quantity} {unit_sym}  [{link_label}]")
        lines.append("")

    return "\n".join(lines)


def _build_inventario_md(
    items: list,
    inventory_unit_registry: InventoryUnitRegistry,
    family_registry: FamilyInventoryRegistry,
) -> str:
    """Build the Inventario tab Markdown, grouped by Perecedero / No Perecedero.

    Pure function — no DataLake access. Groups by fixed category_id (1=Perecedero, 2=No perecedero).
    """
    if not items:
        return "_(Sin artículos de inventario)_"

    perecederos = [i for i in items if i.category_id == 1]
    no_perecederos = [i for i in items if i.category_id == 2]

    lines = []

    def _item_line(item) -> str:
        pu = inventory_unit_registry.get(item.purchase_unit_id)
        su = inventory_unit_registry.get(item.stock_unit_id)
        fam = family_registry.get(item.family_id) if item.family_id else None
        pu_sym = pu.symbol if pu else str(item.purchase_unit_id)
        su_sym = su.symbol if su else str(item.stock_unit_id)
        fam_name = fam.name if fam else "sin familia"
        return (
            f"  - {item.name}   compra: {pu_sym}   stock: {su_sym}   "
            f"factor: {item.purchase_to_stock_factor}   familia: {fam_name}"
        )

    lines.append(f"## Perecederos ({len(perecederos)} artículos)")
    if perecederos:
        for item in perecederos:
            lines.append(_item_line(item))
    else:
        lines.append("  _(sin artículos)_")

    lines.append("")
    lines.append(f"## No Perecederos ({len(no_perecederos)} artículos)")
    if no_perecederos:
        for item in no_perecederos:
            lines.append(_item_line(item))
    else:
        lines.append("  _(sin artículos)_")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers — manual context for agent
# ---------------------------------------------------------------------------

def _build_manual_context(data_lake, session_id: str) -> str:
    """
    Assembles all DataLake entities for a session into a structured plain-text block
    suitable for injection into ManualOperativoAgent's system prompt.

    Returns a minimal placeholder string if the session has no restaurant entity.

    Note: recipe_unit_conversion is a SQLite-only entity type. If the backend is
    ever JSON, the conversion registry will be empty and deductionCoveragePct
    will report 0% regardless of confirmed conversions.

    Single-session MVP assumption: list_entity_ids returns all IDs globally.
    Revisit if multi-session support is added.
    """
    entity_id = stable_entity_id(session_id)

    # Load restaurant
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if not restaurant_data:
        return "Sin datos de restaurante para esta sesión."

    restaurant = restaurant_from_dict(restaurant_data)

    # Load user and classification
    user_data = data_lake.load_entity("user", entity_id) or {}
    classification_data = data_lake.load_entity("classification", entity_id) or {}

    # Load entities
    recipe_unit_ids = data_lake.list_entity_ids("recipe_unit")
    recipe_units = [
        recipe_unit_from_dict(data_lake.load_entity("recipe_unit", uid))
        for uid in recipe_unit_ids
    ]

    inventory_unit_ids = data_lake.list_entity_ids("inventory_unit")
    inventory_units = [
        inventory_unit_from_dict(data_lake.load_entity("inventory_unit", uid))
        for uid in inventory_unit_ids
    ]

    category_ids = data_lake.list_entity_ids("category_recipe")
    categories = [
        category_recipe_from_dict(data_lake.load_entity("category_recipe", cid))
        for cid in category_ids
    ]

    family_ids = data_lake.list_entity_ids("family_inventory")
    families = [
        family_inventory_from_dict(data_lake.load_entity("family_inventory", fid))
        for fid in family_ids
    ]

    recipe_ids = data_lake.list_entity_ids("recipe")
    recipes = [
        recipe_from_dict(data_lake.load_entity("recipe", rid))
        for rid in recipe_ids
    ]

    item_ids = data_lake.list_entity_ids("inventory_item")
    items = [
        inventory_item_from_dict(data_lake.load_entity("inventory_item", iid))
        for iid in item_ids
    ]

    conversion_ids = data_lake.list_entity_ids("recipe_unit_conversion")

    # Build in-memory registries
    recipe_unit_registry = RecipeUnitRegistry()
    for u in recipe_units:
        recipe_unit_registry.add(u)

    inventory_unit_registry = InventoryUnitRegistry()
    for u in inventory_units:
        inventory_unit_registry.add(u)

    category_registry = CategoryRecipeRegistry()
    for c in categories:
        category_registry.add(c)

    family_registry = FamilyInventoryRegistry()
    for f in families:
        family_registry.add(f)

    item_registry = InventoryItemRegistry()
    for item in items:
        item_registry.add(item)

    conversion_table = RecipeUnitConversionRegistry()
    for cid in conversion_ids:
        raw = data_lake.load_entity("recipe_unit_conversion", cid)
        if raw:
            key, entry = recipe_unit_conversion_from_dict(raw)
            conversion_table.add(
                key.recipe_unit_id,
                entry.quantity,
                entry.base_unit_id,
                family_id=key.family_id,
                inventory_item_id=key.inventory_item_id,
                source=entry.source,
            )

    # Compute readiness report
    report = compute_readiness_report(
        restaurant,
        recipes=recipes,
        recipe_unit_registry=recipe_unit_registry,
        inventory_unit_registry=inventory_unit_registry,
        category_recipe_registry=category_registry,
        family_inventory_registry=family_registry,
        inventory_item_registry=item_registry,
        conversion_table=conversion_table,
    )

    # Assemble plain-text context
    operator_name = user_data.get("name", "Operador")
    std_level = classification_data.get("standardization_level", "N/D")
    restaurant_description = classification_data.get("restaurant_description", "")

    lines = []

    lines.append("PERFIL DEL RESTAURANTE")
    lines.append(f"  Nombre: {restaurant.name}")
    lines.append(f"  Tipo: {restaurant.restaurant_type_id}")
    lines.append(f"  Operador: {operator_name}")
    lines.append(f"  Nivel de estandarización: {std_level}")
    if restaurant_description:
        lines.append(f"  Descripción: {restaurant_description}")
    lines.append("")

    overall_data = report.get("overall", {})
    overall = overall_data.get("score_0_100", 0) or 0
    grade = overall_data.get("grade", "N/D")
    lines.append("PUNTUACIÓN DE ESTANDARIZACIÓN")
    lines.append(f"  Puntuación general: {overall:.0f} / 100   Calificación: {grade}")
    for dim in report.get("dimensions", []):
        score = dim.get("score_0_100") or 0
        status = dim.get("status", "na")
        title = dim.get("title", dim.get("dimension_id", ""))
        lines.append(f"  {title}: {score:.0f}%  [{status}]")
    lines.append("")

    fail_warn_kpis = [
        kpi for kpi in report.get("kpis", [])
        if kpi.get("status") in ("fail", "warn")
    ]
    if fail_warn_kpis:
        lines.append("ÁREAS DE OPORTUNIDAD")
        for kpi in fail_warn_kpis:
            lines.append(f"  [{kpi['status'].upper()}] {kpi['title']}")
            evidence_items = kpi.get("evidence", {}).get("sample_missing", [])
            for ev in evidence_items[:5]:
                lines.append(f"    - {ev['ref']}")
        lines.append("")

    lines.append(f"RECETAS ({len(recipes)} total)")
    for recipe in recipes:
        cat_name = ""
        if recipe.category_id is not None:
            cat = category_registry.get(recipe.category_id)
            cat_name = cat.name if cat else str(recipe.category_id)
        lines.append(f"  Receta: {recipe.name}  Categoría: {cat_name}")
        for ing in recipe.ingredients:
            unit = recipe_unit_registry.get(ing.unit_id)
            unit_symbol = unit.symbol if unit else str(ing.unit_id)
            linked_item = item_registry.get_by_name(ing.name)
            link_status = "vinculado" if (ing.inventory_item_id or linked_item) else "sin vincular"
            lines.append(
                f"    - {ing.name}: {ing.quantity} {unit_symbol}  [{link_status}]"
            )
    lines.append("")

    lines.append(f"INVENTARIO ({len(items)} artículos)")
    for item in items:
        pu = inventory_unit_registry.get(item.purchase_unit_id)
        su = inventory_unit_registry.get(item.stock_unit_id)
        fam = family_registry.get(item.family_id) if item.family_id else None
        pu_sym = pu.symbol if pu else str(item.purchase_unit_id)
        su_sym = su.symbol if su else str(item.stock_unit_id)
        fam_name = fam.name if fam else "sin familia"
        lines.append(
            f"  {item.name}  compra: {pu_sym}  stock: {su_sym}  "
            f"factor: {item.purchase_to_stock_factor}  familia: {fam_name}"
        )
    lines.append("")

    lines.append("INSTRUCCIONES PARA DEDUCCIÓN")
    lines.append(
        "  Para calcular ingredientes necesarios: multiplica la cantidad de cada "
        "ingrediente en la receta por el número de porciones solicitadas. "
        "El resultado estará en la unidad de stock del ingrediente. "
        "Para convertir a unidades de compra: divide entre purchase_to_stock_factor. "
        "Si un ingrediente está marcado como 'sin vincular', indícalo explícitamente "
        "en la respuesta."
    )

    context_string = "\n".join(lines)
    return context_string


def render(session_id: gr.State, data_lake) -> None:
    """Stub — replaced by Task 12."""
    gr.Markdown("### Manual operativo\nPendiente — Task 12.")
