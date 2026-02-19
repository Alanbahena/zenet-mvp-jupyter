# Readiness scorecard — UX and presentation

This document defines how to present the readiness score so it feels **trustworthy and not overwhelming**. It complements the KPI schema and computation rules in `.taskmaster/docs/subtask-2.7-plan.md`.

---

## Avoid KPI overload

Do **not** show the full KPI list by default. Users should see a simple, scannable summary first.

### Primary view (default)

1. **One overall grade** (e.g. letter A–D or score 0–100) with a short label (e.g. “Ready”, “Needs work”, “Not ready”).
2. **Four dimension scores** (Phase A: setup, recipes, inventory, normalization). Taxonomy is excluded from the main summary when its weight is 0.
3. **Top 3 fixes** — the 3 most impactful recommendations (from the lowest-scoring KPIs or dimensions). Each item should be one short line and actionable (e.g. “Link ingredients to inventory items”, “Add conversion table entries for X”).

### Secondary view (“View details”)

- Behind a “View details” (or “All KPIs”) control, show the **full KPI list** with status (ok / warn / fail / na), value, and optional evidence/drilldown.
- Keep the primary view visible (e.g. above or in a sidebar) so the user doesn’t lose context.

### Recommendations

- **Source:** Recommendations are derived from failing or warning KPIs; prioritize by impact (e.g. dimension weight × severity).
- **Copy:** Short, actionable. Examples:
  - Low `ingredientsLinkedToInventoryPct` → “Link ingredients to inventory items”
  - Low `deductionCoveragePct` → “Add conversion table entries” or “Fix unit registry/equivalences”
  - Missing setup/registries → “Complete configuration”

---

## Name-based linking (copywriting)

When showing readiness or enrichment metrics that involve “linked to inventory”:

- **Explicit copy:** State that **name-based linking is acceptable but less robust** than linking by `inventory_item_id`. This explains why we still track “% with inventory_item_id set” (enrichment) while counting name-linked ingredients as linked for readiness.
- **Placement:** Use this copy near the recipes/inventory dimension or in a short “How we count links” or tooltip, so power users can trust the score.

---

## Reference

- KPI schema, dimensions, and Phase A defaults: `.taskmaster/docs/subtask-2.7-plan.md`
- Phase A locking: taxonomy weight 0.00, NA handling, truth-KPI targets, and name-based linking rule are defined there.
