# Implementation plan: Subtask 2.6 — Create comprehensive documentation and examples

## Goal

Document the data model, normalization rules, and taxonomy with examples and usage patterns. Verify documentation accuracy and completeness so developers (and AI assistants) can understand and use the core layer confidently.

**Dependencies:** 2.1, 2.2, 2.3, 2.4, 2.5 (all done).

---

## Current state (what exists)

| Asset | Location | Status |
|-------|----------|--------|
| Data model architecture | `docs/Architecture/architecture-data-model.md` | Exists: entity overview, class diagram, template flow, fixed data, registry summary. **Gaps:** `InventoryItemRegistry` not fully documented; no cross-link to normalization/taxonomy. |
| Normalization architecture | `docs/Architecture/architecture-normalization.md` | Exists: layers, conversion flows, deduction pipeline. |
| Taxonomy | `core/taxonomy.py` | Module docstring; no standalone `docs/Architecture/architecture-taxonomy.md`. |
| Data model utils | `core/data_model_utils.py` | Module docstring; no standalone architecture doc. |
| Readiness KPIs | `core/readiness_kpis.py` | Module docstring; schema in `.taskmaster/docs/subtask-2.7-plan.md`; UX in `readiness-scorecard-ux.md`. No `docs/Architecture` doc. |
| README | `README.md` | Exists: purpose, principles, tech stack, getting started. **Gaps:** project structure is outdated (shows nested core/agents, core/workflows; actual structure is flat core/*.py). No dedicated “data model architecture” section. |
| Example code | — | No dedicated runnable examples showing end-to-end usage. |
| Docstrings | `core/*.py` | Module-level docstrings present; class/function docstrings vary. Needs audit. |

---

## Breakdown into steps (do not execute yet)

### Step 2.6.1 — Audit and complete docstrings (core modules)

**Scope:** Ensure all public classes and functions in `core/` have clear docstrings and type hints.

| Module | Actions |
|--------|---------|
| `core/data_model.py` | Audit: Restaurant, Recipe, Ingredient, RecipeUnit, InventoryItem, InventoryUnit, CategoryRecipe, FamilyInventory, InventoryCategory, RestaurantType, User; all registries; template getters. Add/improve docstrings where missing; ensure type hints on public signatures. |
| `core/normalization.py` | Audit: to_base_quantity, from_base_quantity, convert_quantity, get_family_base_unit_id, RecipeUnitConversionRegistry, normalize_recipe_for_deduction, make_resolver, etc. Ensure docstrings explain params, returns, and raised errors. |
| `core/taxonomy.py` | Audit: Taxonomy, IngredientTaxonomy, InventoryTaxonomy, RecipeTaxonomy, find_related_items, IS_A, PART_OF. Add/improve docstrings. |
| `core/data_model_utils.py` | Audit: format_deduction_line_for_display, format_ingredient_for_display, ingredients_to_display, parse_quantity_and_unit, validate_recipe_for_deduction, resolve_ingredient_to_inventory_item, make_resolver_from_item_registry, etc. Ensure docstrings and type hints. |
| `core/readiness_kpis.py` | Audit: compute_readiness_report, EvidenceRef, and key helpers. Ensure docstrings explain inputs, output schema, and Phase A behavior. |

**Output:** Docstrings updated; no functional changes. Linters (if any) pass.

---

### Step 2.6.2 — Update architecture docs (data model, normalization, taxonomy)

**Scope:** Keep `docs/Architecture/` accurate and cross-linked.

| Doc | Actions |
|-----|---------|
| `docs/Architecture/architecture-data-model.md` | Add `InventoryItemRegistry` to registry overview and registry summary table. Add short “Related docs” section linking to architecture-normalization, architecture-taxonomy, and data-model-utils. Optionally add `InventoryUnitEquivalenceRegistry` if not documented. |
| `docs/Architecture/architecture-normalization.md` | Add “Related docs” section linking to architecture-data-model and architecture-taxonomy. Ensure conversion examples (e.g. 1 caja = 10 kg) are present. |
| `docs/Architecture/architecture-taxonomy.md` | **Create.** Explain Taxonomy, IngredientTaxonomy, InventoryTaxonomy, RecipeTaxonomy; is_a / part_of; find_related_items. Include a simple diagram (Mermaid) and usage snippet. |
| `docs/Architecture/architecture-data-model-utils.md` | **Create** (or fold into architecture-data-model). Explain purpose: format/display, validation, resolution, factory helpers. Link to normalization and readiness KPIs where relevant. |
| `docs/Architecture/architecture-readiness-kpis.md` | **Create.** Summary of readiness report schema, dimensions, scoring, and UX guidance. Link to `subtask-2.7-plan.md` and `readiness-scorecard-ux.md` for full spec. |

**Output:** Architecture docs up to date; new docs created where missing.

---

### Step 2.6.3 — Add data model architecture section to README

**Scope:** README should explain the overall data model architecture and design decisions.

| Section | Content |
|---------|---------|
| Data model overview | Short paragraph: entities (Recipe, Ingredient, InventoryItem, etc.), registries, templates, fixed data (RestaurantType, InventoryCategory). |
| Design decisions | Key choices: dataclasses, registries for validation, template-by-restaurant-type, name-based linking for Phase A readiness, etc. |
| Where to read more | Links to `docs/Architecture/architecture-data-model.md`, architecture-normalization, architecture-taxonomy. |
| Project structure (update) | Replace outdated tree with actual structure: `core/data_model.py`, `core/normalization.py`, `core/taxonomy.py`, `core/data_model_utils.py`, `core/readiness_kpis.py`, `docs/Architecture/`, `.taskmaster/docs/`, `tests/unit/`. |

**Output:** README updated; project structure accurate.

---

### Step 2.6.4 — Create example code (usage patterns)

**Scope:** Runnable examples showing common usage patterns.

| Example | Location | Content |
|---------|----------|---------|
| Minimal setup | `docs/examples/minimal_setup.py` or `examples/minimal_setup.py` | Create registries (recipe units, inventory units, categories, families, inventory items); add one recipe with ingredients; show resolution and display formatting. |
| Normalization example | `docs/examples/normalization_example.py` or `examples/normalization_example.py` | Set up conversion table; run normalize_recipe_for_deduction; show deduction lines. |
| Readiness report | `docs/examples/readiness_example.py` or `examples/readiness_example.py` | Build minimal state; call compute_readiness_report; print overall score and key KPIs. |

**Alternatives:**  
- Embed examples in architecture docs as code blocks (ensure they are runnable and tested).  
- Use a single `examples/quickstart.py` that demonstrates data model + normalization + readiness in one flow.

**Output:** At least one runnable example file; examples are tested (e.g. via `python -m py_compile` or a simple smoke test).

---

### Step 2.6.5 — Diagrams for entity relationships and taxonomy

**Scope:** Diagrams already exist in `docs/Architecture/` (Mermaid). Ensure completeness and add taxonomy diagram if missing.

| Diagram | Location | Content |
|---------|----------|---------|
| Entity/registry overview | `architecture-data-model.md` | Already exists (flowchart). |
| Class diagram | `architecture-data-model.md` | Already exists (classDiagram). |
| Template flow | `architecture-data-model.md` | Already exists. |
| Normalization layers | `architecture-normalization.md` | Already exists. |
| Taxonomy hierarchy | `architecture-taxonomy.md` (new) | Add Mermaid diagram: Taxonomy nodes, is_a / part_of edges, example hierarchy (e.g. tomate is_a verdura). |

**Output:** All architecture docs have appropriate diagrams; taxonomy doc includes hierarchy example.

---

### Step 2.6.6 — Verification and checklist

**Test strategy (from task):**

- Verify documentation accuracy by comparing with implementation.
- Test example code to ensure it works as documented.
- Review documentation for completeness and clarity.

**Checklist before marking 2.6 done:**

- [ ] All public classes/functions in core modules have docstrings with type hints (or explicit `None` where applicable).
- [ ] `docs/Architecture/architecture-data-model.md` includes InventoryItemRegistry and cross-links.
- [ ] `docs/Architecture/architecture-taxonomy.md` exists with overview and diagram.
- [ ] `docs/Architecture/architecture-data-model-utils.md` or equivalent exists (or content folded into data-model doc).
- [ ] `docs/Architecture/architecture-readiness-kpis.md` exists with summary and links to full spec.
- [ ] README has “Data model architecture” section and accurate project structure.
- [ ] At least one runnable example (minimal setup, normalization, or readiness) exists and runs without error.
- [ ] No broken internal links in docs.

---

## Suggested order of execution

1. **2.6.1** — Docstring audit (foundation; no doc changes yet).
2. **2.6.2** — Update/create architecture docs.
3. **2.6.3** — Update README.
4. **2.6.4** — Create example code.
5. **2.6.5** — Add/finalize diagrams (can be done as part of 2.6.2).
6. **2.6.6** — Verification and checklist.

---

## Optional / deferred

- **Sphinx/API reference:** Full API docs generation (e.g. `sphinx-build`) can be a later task if needed.
- **Notebook examples:** If preferred over `.py` examples, add `notebooks/examples/` with minimal_setup.ipynb, etc.
- **Spanish translation:** If docs should be bilingual, add `docs/es/` later.

---

## Files to create or modify

| Action | Path |
|--------|------|
| Modify | `core/data_model.py` (docstrings) |
| Modify | `core/normalization.py` (docstrings) |
| Modify | `core/taxonomy.py` (docstrings) |
| Modify | `core/data_model_utils.py` (docstrings) |
| Modify | `core/readiness_kpis.py` (docstrings) |
| Modify | `docs/Architecture/architecture-data-model.md` |
| Modify | `docs/Architecture/architecture-normalization.md` |
| Modify | `README.md` |
| Create | `docs/Architecture/architecture-taxonomy.md` |
| Create | `docs/Architecture/architecture-data-model-utils.md` (or merge into data-model) |
| Create | `docs/Architecture/architecture-readiness-kpis.md` |
| Create | `examples/minimal_setup.py` (or `docs/examples/`) |

---

## Notes for analysis

- **Scope control:** Step 2.6.4 (examples) can be reduced to a single `examples/quickstart.py` if multiple files feel like overkill.
- **Docstring depth:** “Audit” in 2.6.1 means: ensure every public class/function has at least a one-line summary; add param/return/raises where they clarify behavior. No need to document private helpers.
- **Cross-links:** Prefer relative links within docs (e.g. `[architecture-normalization](architecture-normalization.md)`) for portability.
