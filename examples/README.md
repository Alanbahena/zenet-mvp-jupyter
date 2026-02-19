# Examples

Runnable examples for the Zenet MVP core (data model, normalization, readiness).

## quickstart.py

Single flow that demonstrates:

1. **Registries** — Recipe units, inventory units, categories, families, inventory items.
2. **Recipe** — A recipe with ingredients linked to inventory items.
3. **Display** — `ingredients_to_display` and `format_deduction_line_for_display`.
4. **Normalization** — `normalize_recipe_for_deduction` and deduction lines.
5. **Readiness** — `compute_readiness_report` and overall score / KPIs.

**Run from project root:**

```bash
python examples/quickstart.py
```

If the `core` package is not installed (e.g. no `pip install -e .`), use:

```bash
PYTHONPATH=. python examples/quickstart.py
```

**Expected output:** Ingredients list, deduction lines, and a readiness report (status, grade, sample KPIs).

---

## tortilla_example.py

Shows **different-dimension units** and the conversion table:

- **Recipe:** "3 tortillas" in piezas (pza) and "100 g Salsa" in grams.
- **Inventory:** Tortilla stored in kg; Salsa in g.
- **Conversion table:** One entry: 1 pza Tortilla = 0.05 kg, so 3 pza → 0.15 kg for deduction.

**Run from project root:**

```bash
python examples/tortilla_example.py
# or: PYTHONPATH=. python examples/tortilla_example.py
```

**Expected output:** Recipe ingredients (3 pza Tortilla, 100 g Salsa), deduction lines (0.15 kg Tortilla, 100 g Salsa), and a readiness report (status, grade, sample KPIs).
