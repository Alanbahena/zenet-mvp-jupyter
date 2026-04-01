import gradio as gr

from gradio_app.session import stable_entity_id
from core import (
    RecipeUnitRegistry,
    InventoryUnitRegistry,
    CategoryRecipeRegistry,
    FamilyInventoryRegistry,
    InventoryItemRegistry,
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
            for ev in (kpi.get("evidence") or [])[:5]:
                lines.append(f"    - {ev}")
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
