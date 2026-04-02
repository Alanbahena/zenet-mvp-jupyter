import re

import gradio as gr

from gradio_app.session import stable_entity_id
from gradio_app.components import render_chat_panel
from core import (
    RecipeUnitRegistry,
    InventoryUnitRegistry,
    CategoryRecipeRegistry,
    FamilyInventoryRegistry,
    InventoryItemRegistry,
    validate_recipe_for_deduction,
    ManualOperativoAgent,
    create_agent,
    ClaudeProvider,
)
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES
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
    """Build the Resumen tab HTML from a compute_readiness_report() output.

    Pure function — no DataLake access. Returns a non-empty string even when
    all KPIs are na (empty registries / no data).
    """
    blocks = []

    # a) Score hero card
    overall = report.get("overall", {})
    score = overall.get("score_0_100") or 0
    grade = overall.get("grade", "N/D")
    grade_key = (grade or "N")[0]
    grade_color = {"A": "#16a34a", "B": "#2563eb", "C": "#d97706", "D": "#dc2626", "F": "#dc2626"}.get(grade_key, "#6b7280")
    grade_bg    = {"A": "#dcfce7", "B": "#dbeafe", "C": "#fef9c3", "D": "#fee2e2", "F": "#fee2e2"}.get(grade_key, "#f3f4f6")

    blocks.append(
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;'
        f'padding:20px 24px;margin-bottom:20px;display:flex;align-items:center;justify-content:space-between;">'
        f'<div>'
        f'<div style="font-size:0.82em;color:#6b7280;margin-bottom:4px;">Puntuación general</div>'
        f'<div style="font-size:3.2em;font-weight:800;line-height:1;color:#111;">{score:.0f}'
        f'<span style="font-size:0.32em;color:#9ca3af;font-weight:400;"> / 100</span></div>'
        f'</div>'
        f'<div style="text-align:center;">'
        f'<div style="font-size:0.82em;color:#6b7280;margin-bottom:6px;">Calificación</div>'
        f'<div style="background:{grade_bg};color:{grade_color};font-size:2em;font-weight:800;'
        f'width:56px;height:56px;border-radius:50%;display:flex;align-items:center;'
        f'justify-content:center;margin:0 auto;">{grade}</div>'
        f'</div>'
        f'</div>'
    )

    # b) Per-dimension progress bars
    _STATUS_ICON  = {"ok": "&#10003;", "warn": "&#9888;", "fail": "&#10007;"}
    _STATUS_COLOR = {"ok": "#22c55e", "warn": "#f59e0b", "fail": "#ef4444", "na": "#9ca3af"}
    dim_rows = []
    for dim in report.get("dimensions", []):
        if dim.get("dimension_id") in _SKIP_DIMENSIONS:
            continue
        dim_score = dim.get("score_0_100") or 0
        status    = dim.get("status", "na")
        title     = dim.get("title", dim.get("dimension_id", ""))
        icon      = _STATUS_ICON.get(status, "–")
        color     = _STATUS_COLOR.get(status, "#9ca3af")
        dim_rows.append(
            f'<div style="margin:6px 0;">'
            f'<div style="display:flex;align-items:center;gap:10px;">'
            f'<span style="min-width:200px;font-size:0.88em;color:#374151;">{title}</span>'
            f'<div style="flex:1;background:#e5e7eb;border-radius:4px;height:12px;">'
            f'<div style="width:{dim_score:.0f}%;background:{color};border-radius:4px;height:12px;"></div>'
            f'</div>'
            f'<span style="min-width:36px;text-align:right;font-size:0.88em;color:#6b7280;">{dim_score:.0f}%</span>'
            f'<span style="font-size:0.88em;color:{color};">{icon}</span>'
            f'</div>'
            f'</div>'
        )
    if dim_rows:
        blocks.append(
            f'<div style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px 20px;margin-bottom:16px;">'
            f'<div style="font-weight:600;font-size:0.88em;color:#6b7280;letter-spacing:0.05em;margin-bottom:12px;">DIMENSIONES DE ESTANDARIZACIÓN</div>'
            + "".join(dim_rows)
            + f'</div>'
        )

    # c) Deduction coverage highlight
    ded_kpi = next(
        (k for k in report.get("kpis", [])
         if k.get("kpi_id") == "normalization.deductionCoveragePct"),
        None,
    )
    if ded_kpi and ded_kpi.get("status") != "na":
        numerator   = ded_kpi.get("numerator", 0)
        denominator = ded_kpi.get("denominator", 0)
        blocks.append(
            f'<div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;'
            f'padding:10px 16px;margin-bottom:16px;">'
            f'<span style="font-size:0.9em;color:#1e40af;">'
            f'Cobertura de deducción: <strong>{numerator} de {denominator} ingredientes</strong> listos</span>'
            f'</div>'
        )

    # d) Logros as green chips
    logros_text = ["Restaurante registrado", "Nivel de estandarización definido"]
    n_ru = len(recipe_unit_registry.valid_ids())
    if n_ru > 0:
        logros_text.append(f"{n_ru} unidades de receta configuradas")
    n_fam = len({it.family_id for it in items if it.family_id})
    if n_fam > 0:
        logros_text.append(f"{n_fam} familias de inventario configuradas")
    if recipes:
        logros_text.append(f"{len(recipes)} recetas capturadas")
    if items:
        logros_text.append(f"{len(items)} artículos de inventario estructurados")

    chips = "".join(
        f'<span style="background:#dcfce7;color:#15803d;font-size:0.82em;font-weight:500;'
        f'padding:4px 12px;border-radius:999px;display:inline-block;margin:3px 4px 3px 0;">'
        f'&#10003; {t}</span>'
        for t in logros_text
    )
    blocks.append(
        f'<div style="margin-bottom:16px;">'
        f'<div style="font-weight:600;font-size:0.88em;color:#6b7280;letter-spacing:0.05em;margin-bottom:8px;">LOGROS</div>'
        f'<div style="display:flex;flex-wrap:wrap;">{chips}</div>'
        f'</div>'
    )

    # e) Áreas de oportunidad — colored alert cards
    fail_warn = [
        k for k in report.get("kpis", [])
        if k.get("status") in ("fail", "warn")
        and k.get("kpi_id") not in _HIDDEN_KPI_IDS
    ]
    fail_warn.sort(key=lambda k: (
        0 if k["status"] == "fail" else 1,
        0 if k.get("severity") == "high" else 1,
    ))

    area_cards = []
    for kpi in fail_warn[:3]:
        is_fail = kpi["status"] == "fail"
        bg      = "#fef2f2" if is_fail else "#fffbeb"
        border  = "#ef4444" if is_fail else "#f59e0b"
        color   = "#991b1b" if is_fail else "#92400e"
        icon    = "&#10007;" if is_fail else "&#9888;"
        evidence_items = kpi.get("evidence", {}).get("sample_missing", [])
        generic_evs = [ev for ev in evidence_items if ev.get("reason") != _UNIT_MISMATCH_REASON]
        ev_html = "".join(
            f'<div style="font-size:0.83em;color:{color};margin-top:3px;padding-left:10px;">– {ev["ref"]}</div>'
            for ev in generic_evs[:3]
        )
        area_cards.append(
            f'<div style="background:{bg};border-left:3px solid {border};border-radius:6px;'
            f'padding:10px 14px;margin-bottom:8px;">'
            f'<div style="font-weight:600;font-size:0.9em;color:{color};">{icon} {kpi["title"]}</div>'
            f'{ev_html}'
            f'</div>'
        )

    # f) Unit mismatch alert card
    all_mismatch_evs = []
    for kpi in report.get("kpis", []):
        if kpi.get("status") not in ("fail", "warn"):
            continue
        for ev in kpi.get("evidence", {}).get("sample_missing", []):
            if ev.get("reason") == _UNIT_MISMATCH_REASON:
                all_mismatch_evs.append(ev)

    if all_mismatch_evs:
        mismatch_rows = []
        for ev in all_mismatch_evs[:5]:
            ing_name = _parse_ingredient_name_from_ref(ev["ref"])
            ru_sym, iu_sym = _resolve_mismatch_units(
                ing_name, recipes, recipe_unit_registry, item_registry, inventory_unit_registry
            )
            if ru_sym and iu_sym:
                mismatch_rows.append(
                    f'<div style="font-size:0.83em;color:#991b1b;margin-top:3px;padding-left:10px;">'
                    f'– {ing_name}: receta usa "{ru_sym}", inventario usa "{iu_sym}"</div>'
                )
            else:
                mismatch_rows.append(
                    f'<div style="font-size:0.83em;color:#991b1b;margin-top:3px;padding-left:10px;">'
                    f'– {ev["ref"]}</div>'
                )
        area_cards.append(
            f'<div style="background:#fef2f2;border-left:3px solid #ef4444;border-radius:6px;'
            f'padding:10px 14px;margin-bottom:8px;">'
            f'<div style="font-weight:600;font-size:0.9em;color:#991b1b;">&#10007; Ingredientes sin conversión de unidades</div>'
            + "".join(mismatch_rows)
            + f'<div style="font-size:0.8em;color:#b91c1c;margin-top:6px;font-style:italic;">'
            f'Define la equivalencia para que Zenet pueda calcular el consumo.</div>'
            f'</div>'
        )

    if area_cards:
        blocks.append(
            f'<div style="margin-bottom:16px;">'
            f'<div style="font-weight:600;font-size:0.88em;color:#6b7280;letter-spacing:0.05em;margin-bottom:8px;">AREAS DE OPORTUNIDAD</div>'
            + "".join(area_cards)
            + f'</div>'
        )

    return "\n".join(blocks)


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
    type_map = {t.id: t.name for t in DEFAULT_RESTAURANT_TYPES}
    restaurant_type = type_map.get(restaurant.restaurant_type_id, str(restaurant.restaurant_type_id))
    operator = user_data.get("name", "—")
    std_level = classification_data.get("standardization_level", "N/D")
    description = classification_data.get("restaurant_description", "")

    def _field(label: str, value: str) -> str:
        return (
            f'<div style="min-width:160px;">'
            f'<div style="color:#6b7280;font-size:0.8em;margin-bottom:2px;">{label}</div>'
            f'<div style="font-weight:600;font-size:1em;">{value}</div>'
            f'</div>'
        )

    def _stat(label: str, count: int) -> str:
        return (
            f'<div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;'
            f'padding:14px 18px;text-align:center;">'
            f'<div style="font-size:1.8em;font-weight:700;color:#111;">{count}</div>'
            f'<div style="color:#6b7280;font-size:0.82em;margin-top:2px;">{label}</div>'
            f'</div>'
        )

    lines = []

    lines.append(f"## {restaurant.name}")

    # Info fields row
    lines.append(
        f'<div style="display:flex;flex-wrap:wrap;gap:24px;margin:12px 0 8px;">'
        + _field("Tipo de restaurante", restaurant_type)
        + _field("Operador", operator)
        + _field("Nivel de estandarización", str(std_level))
        + f'</div>'
    )

    # Description block
    if description:
        lines.append(
            f'<div style="background:#f0f9ff;border-left:3px solid #38bdf8;'
            f'border-radius:4px;padding:10px 14px;margin:8px 0;'
            f'color:#0369a1;font-size:0.92em;">{description}</div>'
        )

    lines.append("")
    lines.append("**Resumen de configuración**")

    # Stats grid
    lines.append(
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:10px;">'
        + _stat("Recetas", len(recipes))
        + _stat("Artículos de inventario", len(items))
        + _stat("Categorías de receta", len(categories))
        + _stat("Familias de inventario", len(families))
        + _stat("Unidades de receta", len(recipe_units))
        + _stat("Unidades de inventario", len(inventory_units))
        + f'</div>'
    )

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
    """Build the Recetas tab HTML from loaded recipes and registries.

    Pure function — no DataLake access. Badge determined by validate_recipe_for_deduction.
    """
    if not recipes:
        return "_(Sin recetas capturadas)_"

    blocks = []
    for recipe in recipes:
        issues = validate_recipe_for_deduction(
            recipe, item_registry, inventory_unit_registry, conversion_table, family_registry
        )
        ready = not issues

        cat = category_registry.get(recipe.category_id) if recipe.category_id is not None else None
        cat_name = cat.name if cat else "—"

        # Status pill — dark-mode colours
        if ready:
            pill = (
                '<span style="background:#14532d;color:#86efac;font-size:0.78em;'
                'font-weight:600;padding:2px 10px;border-radius:999px;">&#10003; Lista para deducción</span>'
            )
        else:
            pill = (
                '<span style="background:#78350f;color:#fcd34d;font-size:0.78em;'
                'font-weight:600;padding:2px 10px;border-radius:999px;">&#9888; Incompleta</span>'
            )

        # Category chip
        cat_chip = (
            f'<span style="background:#1e3a5f;color:#93c5fd;font-size:0.78em;'
            f'padding:2px 10px;border-radius:999px;margin-left:8px;">{cat_name}</span>'
        )

        # Header row
        header = (
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            f'<span style="font-size:1.05em;font-weight:700;color:#f1f5f9;">{recipe.name}</span>'
            f'{pill}{cat_chip}'
            f'</div>'
        )

        # Description
        desc_html = ""
        if recipe.description:
            desc_html = (
                f'<div style="color:#94a3b8;font-size:0.88em;font-style:italic;'
                f'margin-bottom:10px;">{recipe.description}</div>'
            )

        # Ingredients table
        rows_html = ""
        for i, ing in enumerate(recipe.ingredients):
            unit = recipe_unit_registry.get(ing.unit_id)
            unit_sym = unit.symbol if unit else str(ing.unit_id)
            linked = ing.inventory_item_id is not None or item_registry.get_by_name(ing.name) is not None
            if linked:
                status_cell = '<span style="color:#86efac;font-size:0.85em;">&#9679; vinculado</span>'
            else:
                status_cell = '<span style="color:#fcd34d;font-size:0.85em;">&#9679; sin vincular</span>'
            row_border = "border-top:1px solid #334155;" if i > 0 else ""
            rows_html += (
                f'<tr style="{row_border}">'
                f'<td style="padding:6px 10px 6px 0;font-size:0.9em;color:#e2e8f0;">{ing.name}</td>'
                f'<td style="padding:6px 10px;font-size:0.9em;color:#cbd5e1;">{ing.quantity} {unit_sym}</td>'
                f'<td style="padding:6px 0;font-size:0.9em;">{status_cell}</td>'
                f'</tr>'
            )

        ing_table = (
            f'<table style="width:100%;border-collapse:collapse;border-top:1px solid #334155;margin-top:4px;">'
            f'<thead><tr>'
            f'<th style="text-align:left;font-size:0.75em;color:#94a3b8;padding:6px 10px 6px 0;font-weight:500;">INGREDIENTE</th>'
            f'<th style="text-align:left;font-size:0.75em;color:#94a3b8;padding:6px 10px;font-weight:500;">CANTIDAD</th>'
            f'<th style="text-align:left;font-size:0.75em;color:#94a3b8;padding:6px 0;font-weight:500;">INVENTARIO</th>'
            f'</tr></thead>'
            f'<tbody>{rows_html}</tbody>'
            f'</table>'
        )

        card = (
            f'<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;'
            f'padding:16px 20px;margin-bottom:14px;">'
            f'{header}{desc_html}{ing_table}'
            f'</div>'
        )
        blocks.append(card)

    return "\n".join(blocks)


_INVENTORY_CATEGORY_NAMES = {1: "Perecedero", 2: "No perecedero"}


def _build_inventario_header(perecederos: list, no_perecederos: list) -> str:
    """Return an HTML summary bar for the Inventario tab header.

    Shows total item count + per-category counts.
    Pure function — no DataLake access.
    """
    total = len(perecederos) + len(no_perecederos)
    if total == 0:
        return "_Sin artículos de inventario._"
    return (
        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;'
        f'padding:14px 20px;margin-bottom:16px;display:flex;align-items:center;gap:28px;">'
        f'<div>'
        f'<span style="font-size:1.8em;font-weight:800;color:#111;">{total}</span>'
        f'<span style="font-size:0.85em;color:#6b7280;margin-left:6px;">artículos en total</span>'
        f'</div>'
        f'<div style="width:1px;background:#e5e7eb;height:32px;"></div>'
        f'<div>'
        f'<span style="font-size:1.2em;font-weight:700;color:#15803d;">{len(perecederos)}</span>'
        f'<span style="font-size:0.85em;color:#6b7280;margin-left:6px;">Perecederos</span>'
        f'</div>'
        f'<div>'
        f'<span style="font-size:1.2em;font-weight:700;color:#2563eb;">{len(no_perecederos)}</span>'
        f'<span style="font-size:0.85em;color:#6b7280;margin-left:6px;">No Perecederos</span>'
        f'</div>'
        f'</div>'
    )


def _build_inventario_rows(
    items: list,
    inventory_unit_registry: InventoryUnitRegistry,
    family_registry: FamilyInventoryRegistry,
) -> tuple[list[list], list[list]]:
    """Return (perecederos_rows, no_perecederos_rows) for the Inventario tab.

    Columns: Artículo, Familia, U. Compra, U. Stock, Factor compra→stock.
    Pure function — no DataLake access.
    """
    perecederos = []
    no_perecederos = []
    for item in items:
        pu = inventory_unit_registry.get(item.purchase_unit_id)
        su = inventory_unit_registry.get(item.stock_unit_id)
        fam = family_registry.get(item.family_id) if item.family_id else None
        row = [
            item.name,
            fam.name if fam else "—",
            pu.symbol if pu else str(item.purchase_unit_id),
            su.symbol if su else str(item.stock_unit_id),
            item.purchase_to_stock_factor,
        ]
        if item.category_id == 1:
            perecederos.append(row)
        else:
            no_perecederos.append(row)
    return perecederos, no_perecederos


# ---------------------------------------------------------------------------
# Private helpers — tab content assembly (used by generate_fn)
# ---------------------------------------------------------------------------

def _make_content(data_lake, sid: str) -> tuple[str, str, str, str, list[list], list[list]]:
    """Load entities, build registries, return (resumen, mi_rest, recetas, inv_header, perecederos_rows, no_perecederos_rows).

    Returns placeholder strings/empty lists for all tabs if no restaurant entity exists.
    Pure function with respect to Gradio — no component creation.
    """
    entity_id = stable_entity_id(sid)

    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if not restaurant_data:
        placeholder = "_Sin datos de restaurante. Completa las secciones anteriores primero._"
        return placeholder, placeholder, placeholder, "", [], []

    restaurant = restaurant_from_dict(restaurant_data)
    user_data = data_lake.load_entity("user", entity_id) or {}
    classification_data = data_lake.load_entity("classification", entity_id) or {}

    recipe_units = [
        recipe_unit_from_dict(data_lake.load_entity("recipe_unit", uid))
        for uid in data_lake.list_entity_ids("recipe_unit")
    ]
    inventory_units = [
        inventory_unit_from_dict(data_lake.load_entity("inventory_unit", uid))
        for uid in data_lake.list_entity_ids("inventory_unit")
    ]
    categories = [
        category_recipe_from_dict(data_lake.load_entity("category_recipe", cid))
        for cid in data_lake.list_entity_ids("category_recipe")
    ]
    families = [
        family_inventory_from_dict(data_lake.load_entity("family_inventory", fid))
        for fid in data_lake.list_entity_ids("family_inventory")
    ]
    recipes = [
        recipe_from_dict(data_lake.load_entity("recipe", rid))
        for rid in data_lake.list_entity_ids("recipe")
    ]
    items = [
        inventory_item_from_dict(data_lake.load_entity("inventory_item", iid))
        for iid in data_lake.list_entity_ids("inventory_item")
    ]

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
    for cid in data_lake.list_entity_ids("recipe_unit_conversion"):
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

    resumen = _build_resumen_md(
        report,
        recipe_unit_registry,
        inventory_unit_registry,
        item_registry,
        recipes=recipes,
        items=items,
    )
    mi_rest = _build_mi_restaurante_md(
        restaurant,
        user_data,
        classification_data,
        recipe_units=recipe_units,
        inventory_units=inventory_units,
        categories=categories,
        families=families,
        recipes=recipes,
        items=items,
    )
    recetas = _build_recetas_md(
        recipes, recipe_unit_registry, item_registry,
        category_registry, inventory_unit_registry, conversion_table, family_registry,
    )
    perecederos_rows, no_perecederos_rows = _build_inventario_rows(
        items, inventory_unit_registry, family_registry
    )
    inv_header = _build_inventario_header(perecederos_rows, no_perecederos_rows)

    return resumen, mi_rest, recetas, inv_header, perecederos_rows, no_perecederos_rows


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
    provider = ClaudeProvider()
    agent = create_agent(ManualOperativoAgent, provider=provider, name="manual_operativo")

    def chat_fn(message: str, history: list, sid: str) -> tuple[list, str]:
        context = {"manual_context": _build_manual_context(data_lake, sid)}
        result = agent.run(input_data={"user_message": message}, context=context)
        reply = result.get("reply", "")
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    def generate_fn(sid: str):
        resumen, mi_rest, recetas, inv_header, perecederos, no_perecederos = _make_content(data_lake, sid)
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            resumen,
            mi_rest,
            recetas,
            inv_header,
            perecederos,
            no_perecederos,
        )

    def regen_fn(sid: str):
        return _make_content(data_lake, sid)

    # ------------------------------------------------------------------
    # State 1 — empty state: single generate button
    # ------------------------------------------------------------------
    with gr.Column() as state1_col:
        gr.Markdown("### Manual Operativo")
        gr.Markdown(
            "Genera tu manual operativo una vez que hayas completado las secciones anteriores."
        )
        generate_btn = gr.Button("Generar Manual Operativo", variant="primary")

    # ------------------------------------------------------------------
    # State 2 — generated state (hidden until generate_btn clicked)
    # ------------------------------------------------------------------
    with gr.Column(visible=False) as state2_col:
        regen_btn = gr.Button("Regenerar Manual")
        with gr.Row():
            with gr.Column(scale=7):
                with gr.Tabs():
                    with gr.Tab("Resumen"):
                        resumen_md = gr.Markdown("")
                    with gr.Tab("Mi Restaurante"):
                        mi_rest_md = gr.Markdown("")
                    with gr.Tab("Recetas"):
                        recetas_md = gr.Markdown("")
                    with gr.Tab("Inventario"):
                        inv_header_md = gr.Markdown("")
                        gr.Markdown(
                            '<div style="font-size:1em;font-weight:700;color:#15803d;'
                            'padding-bottom:6px;border-bottom:2px solid #dcfce7;margin-bottom:8px;">'
                            'Perecederos</div>'
                        )
                        perecederos_tbl = gr.Dataframe(
                            headers=["Artículo", "Familia", "U. Compra", "U. Stock", "Factor"],
                            interactive=False,
                            wrap=True,
                        )
                        gr.Markdown(
                            '<div style="font-size:1em;font-weight:700;color:#2563eb;'
                            'padding-bottom:6px;border-bottom:2px solid #dbeafe;margin:16px 0 8px;">'
                            'No Perecederos</div>'
                        )
                        no_perecederos_tbl = gr.Dataframe(
                            headers=["Artículo", "Familia", "U. Compra", "U. Stock", "Factor"],
                            interactive=False,
                            wrap=True,
                        )
            with gr.Column(scale=3):
                gr.Markdown("### Asistente Operativo")
                render_chat_panel(chat_fn, session_id, data_lake)

    generate_btn.click(
        fn=generate_fn,
        inputs=[session_id],
        outputs=[state1_col, state2_col, resumen_md, mi_rest_md, recetas_md, inv_header_md, perecederos_tbl, no_perecederos_tbl],
    )
    regen_btn.click(
        fn=regen_fn,
        inputs=[session_id],
        outputs=[resumen_md, mi_rest_md, recetas_md, inv_header_md, perecederos_tbl, no_perecederos_tbl],
    )
