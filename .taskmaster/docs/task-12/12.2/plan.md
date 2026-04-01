# Subtask 12.2 — Resumen tab: `_build_resumen_md`

## Goal

Implement `_build_resumen_md()` — the pure helper that converts the readiness report
into operator-facing Markdown for the Resumen tab (score, KPI bars, achievements,
áreas de oportunidad, unit mismatch formatting).
Also fix a bug in `_build_manual_context` discovered during cross-referencing.

- **Prior step delivered (12.1):** `_build_manual_context`, `ManualOperativoAgent`,
  `compute_readiness_report()` wired, report structure verified.
- **Next subtask (12.3) needs:** `_build_resumen_md` callable and stable — 12.4 will
  wire it into the generate button handler.

---

## Critical finding — `_build_manual_context` bug (fix in this subtask)

The evidence field in every KPI dict is:
```python
kpi["evidence"] == {"sample_missing": [{"entity_type": str, "ref": str, "reason": str}, ...]}
# OR
kpi["evidence"] == {}   # when no evidence exists
```

The current `_build_manual_context` code does:
```python
for ev in (kpi.get("evidence") or [])[:5]:   # BUG
```

- When `evidence == {}` (falsy) → `{} or []` = `[]` → silent (no evidence shown, acceptable)
- When `evidence == {"sample_missing": [...]}` (truthy) → tries `{"sample_missing": [...]}[:5]`
  → **raises `TypeError: unhashable type: 'slice'`** at runtime

This will crash as soon as any recipe has unlinked ingredients. Fix as Step 1 of this subtask.

**Correct evidence access pattern:**
```python
evidence_items = kpi.get("evidence", {}).get("sample_missing", [])
for ev in evidence_items[:5]:
    # ev == {"entity_type": str, "ref": str, "reason": str}
    lines.append(f"    - {ev['ref']}")
```

---

## Evidence structure (from `readiness_kpis.py`)

`EvidenceRef` dataclass (converted to dict via `asdict`):
```python
{
    "entity_type": str,   # e.g. "ingredient", "recipe", "inventory_item"
    "ref":         str,   # e.g. "Recipe#1: 'tortillas'"  (human-readable pointer)
    "reason":      str,   # e.g. "Missing conversion entry (...)"
}
```

All KPI builders (`_ratio_kpi`, `_count_kpi`) store evidence as:
```python
"evidence": {"sample_missing": [asdict(x) for x in items[:5]]} if evidence else {}
```

---

## Unit mismatch reason string (exact)

```
"Missing conversion entry (ingredient unit family differs from inventory item unit family)"
```

This is the string returned by `_classify_normalization_skip_reason()` at line 1111
of `readiness_kpis.py` when recipe unit and inventory item stock unit are in different
measurement dimensions (e.g. pza vs kg).

---

## Files to create / modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/manual_operativo.py` | Modify | Fix evidence bug in `_build_manual_context`; add `_build_resumen_md` |

---

## Dependencies

- Subtask 12.1 done
- Report structure verified: `report["overall"]["score_0_100"]`, `report["overall"]["grade"]`,
  `report["dimensions"]` (list), `report["kpis"]` (list)
- `EvidenceRef` dict structure confirmed: `entity_type`, `ref`, `reason`
- `RecipeUnitRegistry.get(unit_id)` → `RecipeUnit | None` (`.symbol` field)
- `InventoryUnitRegistry.get(unit_id)` → `InventoryUnit | None` (`.symbol` field)
- `InventoryItemRegistry.get_by_name(name)` → `InventoryItem | None` (`.stock_unit_id` field)

---

## Key design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Pure function | Takes report + registries, returns str | Keeps rendering logic testable without DataLake |
| Signature includes `item_registry` | Yes | Needed to resolve inventory item `stock_unit_id` for unit mismatch display |
| Progress bars | Unicode blocks `████░░░░` in Markdown | No native Gradio static progress bar |
| Taxonomy dimension | Skip in bar rendering | Weight=0, always `na`, meaningless to show |
| Deduction coverage | Show as "X de Y ingredientes" | `deductionCoveragePct` is ingredient-level; `numerator`/`denominator` fields available directly |
| Logros completados | Hardcoded conditions from entity counts | Avoids re-parsing KPI logic; 6 fixed logros per parent plan |
| Top áreas de oportunidad | Max 3 from fail/warn KPIs, sorted by severity | Enough to be actionable, not overwhelming |
| Unit mismatch block | Separate formatted section | Different enough from generic evidence to warrant its own display |

---

## Implementation steps

### Step 1 — Fix bug in `_build_manual_context`

In `gradio_app/sections/manual_operativo.py`, replace the broken evidence loop:

```python
# BEFORE (buggy — crashes when evidence is non-empty dict)
for ev in (kpi.get("evidence") or [])[:5]:
    lines.append(f"    - {ev}")

# AFTER (correct)
evidence_items = kpi.get("evidence", {}).get("sample_missing", [])
for ev in evidence_items[:5]:
    lines.append(f"    - {ev['ref']}")
```

### Step 2 — Add `_build_resumen_md` to `manual_operativo.py`

Signature:
```python
def _build_resumen_md(
    report: dict,
    recipe_unit_registry: RecipeUnitRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
    item_registry: InventoryItemRegistry,
    *,
    recipes: list,
    items: list,
) -> str:
    """
    Build the Resumen tab Markdown from a compute_readiness_report() output.

    Pure function — no DataLake access. Returns a non-empty string even when
    all KPIs are na (empty registries / no data).
    """
```

Build in this order:

**a) Header and overall score**
```python
overall = report.get("overall", {})
score = overall.get("score_0_100") or 0
grade = overall.get("grade", "N/D")
# Output:
# ## Tu restaurante está estandarizado
# **Puntuación general: 78 / 100 — Calificación: B**
```

**b) Per-dimension progress bars**
```python
_SKIP_DIMENSIONS = {"taxonomy"}  # weight=0, always na — omit

for dim in report.get("dimensions", []):
    if dim.get("dimension_id") in _SKIP_DIMENSIONS:
        continue
    score = dim.get("score_0_100") or 0
    status = dim.get("status", "na")
    title = dim.get("title", dim.get("dimension_id", ""))
    filled = round(score / 5)           # 0–20 blocks
    bar = "█" * filled + "░" * (20 - filled)
    icon = {"ok": "✓", "warn": "⚠", "fail": "✗"}.get(status, "-")
    # Output: "`Configuración`   ████████████████████  100%  ✓"
```

**c) Deduction coverage line**
```python
ded_kpi = next(
    (k for k in report.get("kpis", [])
     if k.get("kpi_id") == "normalization.deductionCoveragePct"),
    None,
)
if ded_kpi and ded_kpi.get("status") != "na":
    numerator = ded_kpi.get("numerator", 0)
    denominator = ded_kpi.get("denominator", 0)
    # Output: "Cobertura de deducción: 9 de 15 ingredientes listos"
```

**d) Logros completados**

Fixed list of 6 logros, each shown only if the condition is met:
```python
logros = []
logros.append("✓ Restaurante registrado")               # always (we have the entity)
logros.append("✓ Nivel de estandarización definido")    # always
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
```

Note: `RecipeUnitRegistry.valid_ids()` returns a `set[int]`. Confirmed at
`data_model.py` line 619–621. Method name is `valid_ids()` — NOT `list_ids()`.

**e) Áreas de oportunidad — generic**

```python
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

fail_warn = [
    k for k in report.get("kpis", [])
    if k.get("status") in ("fail", "warn")
    and k.get("kpi_id") not in _HIDDEN_KPI_IDS
]
# Sort: fail before warn, high severity before low
fail_warn.sort(key=lambda k: (0 if k["status"] == "fail" else 1,
                               0 if k.get("severity") == "high" else 1))

for kpi in fail_warn[:3]:
    icon = "✗" if kpi["status"] == "fail" else "⚠"
    evidence_items = kpi.get("evidence", {}).get("sample_missing", [])

    # Separate unit mismatch items from generic items
    mismatch_evs = [ev for ev in evidence_items if ev.get("reason") == _UNIT_MISMATCH_REASON]
    generic_evs  = [ev for ev in evidence_items if ev.get("reason") != _UNIT_MISMATCH_REASON]

    if generic_evs:
        # Output: "✗ Ingredientes sin vincular al inventario:"
        #         "  - Recipe#1: 'tortillas'"
        for ev in generic_evs[:3]:
            lines.append(f"  - {ev['ref']}")
```

**f) Áreas de oportunidad — unit mismatch block**

Collect ALL unit mismatch evidence across ALL fail/warn normalization KPIs (not just top 3):

```python
all_mismatch_evs = []
for kpi in report.get("kpis", []):
    if kpi.get("status") not in ("fail", "warn"):
        continue
    for ev in kpi.get("evidence", {}).get("sample_missing", []):
        if ev.get("reason") == _UNIT_MISMATCH_REASON:
            all_mismatch_evs.append(ev)

if all_mismatch_evs:
    lines.append("✗ Ingredientes sin conversión de unidades definida:")
    for ev in all_mismatch_evs[:5]:
        # ev["ref"] == "Recipe#1: 'tortillas'"
        # Parse ingredient name from ref to look up unit_id:
        ing_name = _parse_ingredient_name_from_ref(ev["ref"])
        recipe_unit_sym, inv_unit_sym = _resolve_mismatch_units(
            ing_name, recipes, recipe_unit_registry, item_registry, inventory_unit_registry
        )
        if recipe_unit_sym and inv_unit_sym:
            lines.append(f"  → {ing_name}: receta usa \"{recipe_unit_sym}\", inventario usa \"{inv_unit_sym}\"")
        else:
            lines.append(f"  → {ev['ref']}")
    lines.append("  *(Define la equivalencia para que Zenet pueda calcular el consumo)*")
```

**g) Two private helpers for unit mismatch resolution**

Add `import re` at the top of the file (module level), alongside existing imports.

Define `_SKIP_DIMENSIONS`, `_HIDDEN_KPI_IDS`, and `_UNIT_MISMATCH_REASON` as
module-level constants (below imports, above functions) so they are accessible
to tests and both helper functions.

```python
def _parse_ingredient_name_from_ref(ref: str) -> str:
    """Extract ingredient name from EvidenceRef.ref string like "Recipe#1: 'tortillas'"."""
    # ref format: "Recipe#N: 'ingredient_name'" (ing.name via repr())
    m = re.search(r":\s*'(.+)'$", ref)
    return m.group(1) if m else ref


def _resolve_mismatch_units(
    ing_name: str,
    recipes: list,
    recipe_unit_registry: RecipeUnitRegistry,
    item_registry: InventoryItemRegistry,
    inventory_unit_registry: InventoryUnitRegistry,
) -> tuple[str | None, str | None]:
    """
    Return (recipe_unit_symbol, inventory_unit_symbol) for a unit mismatch ingredient.
    Returns (None, None) if the ingredient or linked item cannot be found.
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
```

### Step 3 — Add `InventoryItemRegistry` to imports in `_build_resumen_md`

`InventoryItemRegistry` is already imported at the top of the file (added in 12.1).
No new imports needed.

---

## Out of scope (12.2)

- `render()` — deferred to 12.4
- Mi Restaurante, Recetas, Inventario tabs — deferred to 12.3
- Agent sidebar wiring — deferred to 12.4
- Two-state generate button — deferred to 12.4
- All tests — deferred to 12.5

---

## Test coverage

All tests deferred to subtask 12.5. No test file created here.

Mocked tests (12.5):
- `test_build_resumen_md_all_na_kpis` — empty registries + all-na report → non-empty string, "0 / 100", no crash
- `test_build_resumen_md_score_and_grade` — score=78, grade="B" → string contains "78" and "B"
- `test_build_resumen_md_progress_bars` — dimension score=100 → 20 filled blocks (`█` × 20)
- `test_build_resumen_md_skips_taxonomy` — taxonomy dimension present → not in output
- `test_build_resumen_md_areas_of_opportunity` — 1 fail KPI with evidence → `ev["ref"]` appears in output
- `test_build_resumen_md_unit_mismatch` — normalization KPI with unit mismatch evidence + matching recipe in `recipes` → "receta usa X, inventario usa Y" appears
- `test_build_manual_context_evidence_fix` — KPI with non-empty evidence dict → no TypeError, `ref` values appear in output

Live tests: none (pure Markdown generation, no external API).

---

## Risks and open questions

### [OPEN] — Double data loading in 12.4 generate handler
**Source:** Validation of subtask 12.2
**Problem:** `_build_resumen_md` needs registries and entity lists. `_build_manual_context` loads the same entities from DataLake. The 12.4 generate handler will call both, loading DataLake twice.
**Impact:** Doubled SQLite reads on every "Generar Manual" click. Negligible at Phase A scale but architecturally redundant.
**Suggested action:** In 12.4, extract a shared `_load_session_data(data_lake, session_id)` helper that returns all registries + entity lists. Both functions receive the loaded data instead of re-loading. Add note to 12.4 plan.

- **`_parse_ingredient_name_from_ref` regex** — Evidence `ref` format is `"Recipe#N: 'ingredient_name'"`. If the ingredient name contains a single quote, the regex will fail. For MVP this is acceptable; document as a known limitation.

- **`InventoryItemRegistry.get(id)`** — verify this method exists. The plan uses `item_registry.get(ing.inventory_item_id)` but `data_model.py` may expose a different method name. Cross-check before implementing.

- **`list_ids()` on `RecipeUnitRegistry`** — returns `set[int]` (from `data_model.py` line 621: `return {u.id for u in self._units}`). `len(list(...))` works but `len(registry.list_ids())` is simpler.

---

## Deliverable checklist

`gradio_app/sections/manual_operativo.py`:
- [ ] Bug fixed in `_build_manual_context`: evidence access uses `kpi.get("evidence", {}).get("sample_missing", [])` and `ev["ref"]` for display
- [ ] `_build_resumen_md(report, recipe_unit_registry, inventory_unit_registry, item_registry, *, recipes, items) -> str` added
- [ ] Header: overall score from `report["overall"]["score_0_100"]` and grade
- [ ] Per-dimension Unicode progress bars (20 blocks), taxonomy dimension skipped
- [ ] Status icons: `✓` ok, `⚠` warn, `✗` fail
- [ ] Deduction coverage line: "X de Y ingredientes listos" from `numerator`/`denominator` fields of `normalization.deductionCoveragePct` KPI; omitted if status is `na`
- [ ] Logros completados: 6-item checklist with entity counts
- [ ] Áreas de oportunidad: top 3 fail/warn KPIs (hidden KPIs excluded), evidence items from `sample_missing`
- [ ] Unit mismatch block: separate section with plain-language "receta usa X, inventario usa Y" when unit IDs can be resolved; fallback to `ev["ref"]` otherwise
- [ ] `_parse_ingredient_name_from_ref(ref: str) -> str` private helper
- [ ] `_resolve_mismatch_units(...) -> tuple[str | None, str | None]` private helper
- [ ] Returns non-empty string for empty registries / all-na report (no crash)
- [ ] stub `render()` left unchanged
