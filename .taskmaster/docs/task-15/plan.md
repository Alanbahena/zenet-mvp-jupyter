# Task 15 — Unit and Integration Tests

## Context

This task is the quality gate before Task 16 (Documentation) and Task 18 (ngrok demo).
Tasks 7–12 produced 21 test files under `tests/unit/`. Three of those tests are currently
broken due to implementation changes made during Task 12, and test coverage for
`readiness_kpis.py` is thin (3 tests). This plan fixes both gaps.

**Note:** The `tasks.json` details block for task 15 is outdated — it references
`NotebookOrchestrator`, `Workflow`, and other classes from cancelled tasks 13 and 14
that were never built. The actionable scope is derived from the actual codebase state
as of task 12 completion.

---

## Scope

### In scope

1. Fix 3 broken items in `tests/unit/test_manual_operativo.py` (import rename + 2 HTML assertion mismatches introduced during Task 12 UI redesign).
2. Expand `tests/unit/test_readiness_kpis.py` with 3 additional edge-case tests.
3. Verify full `pytest tests/` suite passes with no regressions.

### Out of scope

- `tests/integration/` directory — references cancelled tasks 13/14.
- `tests/system/` directory — references non-existent `NotebookOrchestrator`.
- New test files for modules that already have coverage (`core/ai/providers.py`, `core/agents/base_agent.py`, etc.).
- Any changes to production code in `core/` or `gradio_app/`.

---

## Root Cause of Broken Tests

During Task 12 (Manual Operativo), two changes broke existing tests:

| Change | Broken test |
|--------|-------------|
| `_build_inventario_md` renamed to `_build_inventario_rows` (returns `tuple[list,list]` instead of `str`) | `TestBuildInventarioMd.test_groups_by_category` — import fails on line 38 |
| Score hero card wraps score in HTML: `<div>0<span> / 100</span></div>` | `TestBuildResumenMd.test_all_na_kpis_renders_zero_score` — `assertIn("0 / 100", result)` fails |
| Ingredient link status uses HTML entity `&#9679; vinculado` instead of plain `✓ vinculado` | `TestBuildRecetasMd.test_linked_ingredient_shows_vinculado` — assertion fails |

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `tests/unit/test_manual_operativo.py` | Modify | Fix import + 2 assertion mismatches |
| `tests/unit/test_readiness_kpis.py` | Modify | Add 3 edge-case tests |

---

## Implementation Steps

### Step 1 — Fix `tests/unit/test_manual_operativo.py`

**1a. Line 38 — import rename**

Replace:
```python
from gradio_app.sections.manual_operativo import (
    _build_inventario_md,
    _build_manual_context,
    _build_recetas_md,
    _build_resumen_md,
)
```
With:
```python
from gradio_app.sections.manual_operativo import (
    _build_inventario_header,
    _build_inventario_rows,
    _build_manual_context,
    _build_recetas_md,
    _build_resumen_md,
)
```

**1b. `TestBuildInventarioMd` — rewrite for tuple return**

`_build_inventario_rows` returns `(perecederos_rows, no_perecederos_rows)` where each is
`list[list]` with columns `[name, family, u_compra, u_stock, factor]`.

Replace the test body to assert on tuple contents:
```python
def test_groups_by_category(self):
    item_p  = InventoryItem(id=1, name="Carne", stock_unit_id=1, purchase_unit_id=1, category_id=1)
    item_np = InventoryItem(id=2, name="Sal",   stock_unit_id=1, purchase_unit_id=1, category_id=2)
    perecederos, no_perecederos = _build_inventario_rows(
        [item_p, item_np], InventoryUnitRegistry(), FamilyInventoryRegistry()
    )
    self.assertEqual(len(perecederos), 1)
    self.assertEqual(len(no_perecederos), 1)
    self.assertEqual(perecederos[0][0], "Carne")
    self.assertEqual(no_perecederos[0][0], "Sal")
```

**1c. `TestBuildResumenMd.test_all_na_kpis_renders_zero_score` — HTML-aware assertion**

The score and "/ 100" are in separate HTML elements and will not appear as the literal
substring `"0 / 100"`. Split into two checks:

```python
self.assertIn(">0<", result)      # score digit
self.assertIn("/ 100", result)    # denominator text
```

**1d. `TestBuildRecetasMd.test_linked_ingredient_shows_vinculado` — HTML entity**

```python
# Before
self.assertIn("✓ vinculado", result)
# After
self.assertIn("&#9679; vinculado", result)
```

---

### Step 2 — Expand `tests/unit/test_readiness_kpis.py`

Add a new test class `TestReadinessReportSchema` with three tests:

**2a. `test_empty_registries_returns_na_overall`**

Call `compute_readiness_report` with a minimal `Restaurant` and all empty registries.
Assert:
- `report["overall"]["score_0_100"]` is `0` or `None`
- `report["overall"]["grade"]` is `"N/D"` or `None`
- All dimension statuses are `"na"`

**2b. `test_report_has_required_top_level_keys`**

Call with empty registries. Assert all five top-level keys are present:
`schema_version`, `generated_at`, `overall`, `dimensions`, `kpis`

**2c. `test_deduction_coverage_kpi_is_present`**

Call with empty registries. Assert that `kpi_id == "normalization.deductionCoveragePct"`
appears in the `kpis` list.

---

### Step 3 — Verify

```bash
# Target files first
uv run python -m pytest tests/unit/test_manual_operativo.py tests/unit/test_readiness_kpis.py -v

# Full suite — confirm no regressions
uv run python -m pytest tests/ -v
```

---

## Test Coverage Summary

All tests are offline (mocked). No external services required.

| File | Before | After |
|------|--------|-------|
| `test_manual_operativo.py` | 3 broken, 9 passing, 2 live-skipped | 0 broken, 12 passing, 2 live-skipped |
| `test_readiness_kpis.py` | 3 tests | 6 tests |

Live tests in `TestManualOperativoAgentLive` (2 tests, guarded by `ANTHROPIC_API_KEY`) will
begin passing once the import error on line 38 is resolved.

---

## Deliverable Checklist

`tests/unit/test_manual_operativo.py`
- [ ] Import block updated: `_build_inventario_md` → `_build_inventario_rows` + `_build_inventario_header`
- [ ] `TestBuildInventarioMd.test_groups_by_category` rewritten for `tuple[list, list]` return type
- [ ] `TestBuildResumenMd.test_all_na_kpis_renders_zero_score` assertion split: `">0<"` + `"/ 100"`
- [ ] `TestBuildRecetasMd.test_linked_ingredient_shows_vinculado` assertion: `"&#9679; vinculado"`

`tests/unit/test_readiness_kpis.py`
- [ ] `test_empty_registries_returns_na_overall` added
- [ ] `test_report_has_required_top_level_keys` added
- [ ] `test_deduction_coverage_kpi_is_present` added

Verification
- [ ] `pytest tests/unit/test_manual_operativo.py` — all 12 mocked tests pass
- [ ] `pytest tests/unit/test_readiness_kpis.py` — all 6 tests pass
- [ ] `pytest tests/` — full suite green, no regressions

---

## Risks and Open Questions

### [OPEN] — Empty-registry overall status is "ok", not "na"
**Source:** Validation of task 15
**Problem:** `_worst_status([])` defaults to `"ok"` (`readiness_kpis.py:276`). When all registries are empty, all dimension statuses are `"na"` (correct), but `report["overall"]["status"]` is `"ok"` — not `"na"` or `"fail"`. Step 2a's prose description could mislead an implementer into asserting `overall["status"] == "na"`, which would fail.
**Impact:** A naively written assertion fails with no obvious explanation, wasting debugging time.
**Suggested action:** Add a comment to step 2a: "Do not assert `overall['status']` — it is `'ok'` when the filtered status list is empty (expected behavior)." Defer any behavior change to task 16 if desired.
