# Plan: Inventory unit information and equivalences

## Context

- **Current workflow:** When a user adds an ingredient to a recipe and the ingredient is **new**, the system creates an **InventoryItem**. The item needs: name, **unit_id** (InventoryUnit), category_id (perecedero/no perecedero from LLM), optional family_id.
- **Gap:** The 2.2 plan leaves **how the user provides or selects the inventory unit** when creating an InventoryItem only partially specified (optional `unit_id_for_inventory` in add_ingredient). There is no explicit flow for “user adds inventory unit information” or for **equivalence** between units (e.g. 1 kg = 1000 g) and an **equivalence unit** (reference unit for display or conversion).

This document plans both: (1) **how the user adds/selects inventory unit information**, and (2) **equivalence and equivalence unit** in a coherent way.

---

## Part 1 — How the user adds inventory unit information

### 1.1 Two places where “inventory unit” appears

| Place | Who provides it | Notes |
|-------|-----------------|--------|
| **Configuration (unit registry)** | User (or template) | User adds/edits/removes **InventoryUnit** entities (e.g. kg, L, caja, bolsa). Already in 2.2: InventoryUnitRegistry with add/remove and valid_inventory_unit_ids(). |
| **Creating an InventoryItem** | User or system | Each InventoryItem has a **unit_id** (InventoryUnit). Must be from valid_inventory_unit_ids. |

So “adding inventory unit **information**” can mean:
- **A)** Adding new **InventoryUnit** definitions (name, symbol) in Configuration.
- **B)** Assigning the **unit_id** when creating or editing an InventoryItem (from new ingredient or directly in inventory).

Both should be planned explicitly.

---

### 1.2 A) Adding InventoryUnit definitions (Configuration)

- **Where:** Configuration agent / Configuration screen; unit registry (2.2).
- **Flow:**
  1. User (or template) has a set of **InventoryUnit** entities (e.g. from templates-recipe-and-inventory: kg, L, ml, pza, caja, bolsa, bote).
  2. User can **add** a new unit: name + symbol (and optional description). Registry assigns id and adds to list.
  3. User can **edit** name/symbol/description or **remove** a unit (with guard: “in use” by at least one InventoryItem → warn or block removal, or demote to “archived”).
- **Already in 2.2:** InventoryUnitRegistry: add_inventory_unit(unit), remove_inventory_unit(unit_id), valid_inventory_unit_ids(). So the **plan** here is: ensure the **UI/agent** exposes “add inventory unit” and “edit/remove inventory unit” using that registry; templates pre-fill so the user often only adds exceptions.

**Recommendation:** No change to the data model. Document in Configuration flow: “User can add, edit, remove inventory units; valid_inventory_unit_ids() is the source of truth for unit_id when creating InventoryItems.”

---

### 1.3 B) Assigning unit_id when creating an InventoryItem

An InventoryItem is created in two ways:

- **From a new ingredient (add_ingredient workflow):** Ingredient has a **RecipeUnit** (e.g. gramo). InventoryItem needs an **InventoryUnit** (e.g. kg or gramo if it exists in inventory units). So we need a rule for “which InventoryUnit to use.”
- **Direct creation:** User adds an inventory item manually; they must choose a unit from the inventory unit list.

**Proposed rules:**

1. **Direct creation (manual add to inventory)**  
   - User **must select** one unit from the list of valid InventoryUnits (dropdown / autocomplete from valid_inventory_unit_ids()).  
   - No default except possibly “most used” or first in list; product can define a simple default (e.g. “kg” or “pza”).

2. **Creation from new ingredient (add_ingredient)**  
   - **Option A (recommended):** Caller (Structuring agent / service) **must pass** `unit_id_for_inventory: int` when creating the new InventoryItem (from the set valid_inventory_unit_ids()). The UI/agent decides the value by:
     - **Same-unit rule:** If the ingredient’s RecipeUnit has the same symbol as an InventoryUnit (e.g. “g” → “g”), use that InventoryUnit’s id.
     - **User choice:** If the user is prompted (“This ingredient will be tracked in inventory. In which unit?”), show dropdown of InventoryUnits and use selection.
     - **LLM or default:** LLM suggests an inventory unit from context (e.g. “harina” → kg); or product default (e.g. solids → kg, liquids → L).
   - **Option B:** If `unit_id_for_inventory` is omitted, **require** a later step to set the unit before the item is considered “complete,” or use a strict default (e.g. first inventory unit). Prefer **Option A** so every new InventoryItem has an explicit, valid unit at creation.

**Plan summary for “user adds inventory unit information”:**

- **Configuration:** User adds/edits/removes **InventoryUnit** entities via InventoryUnitRegistry (2.2); templates pre-fill; UI/agent exposes add/edit/remove.
- **When creating an InventoryItem from new ingredient:** Require `unit_id_for_inventory` (from valid_inventory_unit_ids). UI/agent derives it by: same-unit match (recipe unit symbol = inventory unit symbol), or user selection, or LLM/default. Document this in 2.2 and in the Structuring/Configuration flow.
- **When creating an InventoryItem directly:** User selects unit from valid InventoryUnits (dropdown / list).

This keeps a single source of truth (InventoryUnit registry) and a clear rule for both creation paths.

---

## Part 2 — Equivalence and equivalence unit (coherent breakdown)

### 2.1 What “equivalence” and “equivalence unit” mean

- **Equivalence:** A numeric relationship between two units of the same “kind” (e.g. 1 kg = 1000 g, 1 L = 1000 ml). Used for conversion when displaying, normalizing, or matching recipe quantities to inventory.
- **Equivalence unit (reference unit):** A chosen unit used as the **reference** for an item or for a unit family (e.g. “gram” as base for mass; “liter” for volume). Conversions can be expressed as “1 unit X = factor × reference_unit.”

So we need:
1. A **data model** for equivalences between units.
2. A **scope** (recipe units only, inventory units only, or both; and whether we need recipe ↔ inventory).
3. Optional: **per-item “display” or “reporting” unit** (equivalence unit for an InventoryItem).

---

### 2.2 Data model for equivalences

**Option A — Per-unit base + factor (recommended for MVP)**

- Each **RecipeUnit** and each **InventoryUnit** can optionally reference a **base unit** and a **factor**:
  - `base_unit_id: int | None` (same type: RecipeUnit.id or InventoryUnit.id).
  - `factor_to_base: float` (e.g. 1 kg → base g, factor_to_base = 1000; 1 g → base g, factor_to_base = 1).
- Conversion: `quantity_in_base = quantity * factor_to_base` (and inverse when needed).
- **Pros:** Simple, one place per unit; easy to convert to a single reference. **Cons:** Only one “direction” per unit (to base); if we need many pairwise conversions, we go through base.

**Option B — Explicit pairwise equivalence table**

- New entity: **UnitEquivalence** (or equivalent): `from_unit_id`, `to_unit_id`, `factor` (1 from_unit = factor × to_unit). Could be for RecipeUnit pairs, InventoryUnit pairs, or both.
- **Pros:** Flexible, multiple reference units possible. **Cons:** More entities; consistency (e.g. 1 kg = 1000 g and 1 g = 0.001 kg) must be maintained or derived.

**Recommendation for coherence:** Start with **Option A** (base_unit_id + factor_to_base) on **InventoryUnit** (and later, if needed, on RecipeUnit). So:

- **InventoryUnit** gets optional: `base_unit_id: Optional[int] = None`, `factor_to_base: float = 1.0`.
  - If `base_unit_id is None`, treat the unit as its own base (factor_to_base 1.0).
  - Example: gramo (id=1) base_unit_id=None, factor_to_base=1; kilogramo (id=2) base_unit_id=1, factor_to_base=1000.
- **RecipeUnit** can get the same fields in a later step when we do recipe-unit normalization (2.3).

Equivalence **unit** (the “reference” unit) is then: the unit that has `base_unit_id is None` in its “family” (or the canonical base for that dimension). So the **equivalence unit** is just the base unit we use for that group (e.g. gram for mass, liter for volume).

---

### 2.3 Scope and where to implement

| Scope | Where | When (task) |
|-------|--------|-------------|
| InventoryUnit equivalences | core/data_model.py (add base_unit_id, factor_to_base to InventoryUnit); conversion helper in registry or data_model_utils | 2.2 (minimal) or 2.3 (normalization) |
| RecipeUnit equivalences | Same idea on RecipeUnit | 2.3 (normalization) |
| Cross (recipe ↔ inventory) | Conversion only when linking ingredient (recipe unit) to inventory (inventory unit); use two bases and a bridge or same base if we unify | 2.3 |

**Recommendation:** In **2.2** we only **document** that InventoryUnit (and later RecipeUnit) will support optional base_unit_id and factor_to_base for equivalences; implement in **2.3** (normalization) so conversion logic lives in one place. If we want a minimal 2.2 placeholder: add the two optional fields to InventoryUnit and a simple `to_base_quantity(quantity: float) -> float` helper that uses factor_to_base and recurses to base_unit.

---

### 2.4 “Equivalence unit” on InventoryItem (optional)

- **Meaning:** “Display or report this item in this unit” (e.g. item stored in kg, but show in g for some screens).
- **Model:** Optional on InventoryItem: `display_unit_id: Optional[int] = None` (InventoryUnit id). If set, UI can convert stored quantity to display_unit_id for display using the equivalence model above.
- **Plan:** Defer to after Part 2.2 is implemented. Then: add `display_unit_id` to InventoryItem; when displaying, if set, convert using unit equivalences. So: **Phase 1** = unit-level equivalences (base_unit_id, factor_to_base); **Phase 2** = optional display_unit_id on InventoryItem and use equivalences for display.

---

### 2.5 User flow for equivalences

- **Configuration:** User can **edit** an InventoryUnit to set “base unit” and “factor to base” (e.g. kg → base gramo, factor 1000). Or we ship with a **template** of common equivalences (g, kg, L, ml, etc.) so the user rarely adds them.
- **Validation:** base_unit_id must be in valid_inventory_unit_ids(); factor_to_base > 0; avoid cycles (unit A → base B, B → base A).
- **Use:** When we need to convert (e.g. “how many grams is 0.5 kg?”), use to_base_quantity(0.5, unit_kg) → 500 (in base g). Equivalence unit for that family is the base unit (e.g. gramo).

---

## Part 3 — Coherent implementation order

1. **2.2 (current)**  
   - Keep InventoryUnitRegistry; ensure add_ingredient workflow **requires** or strongly recommends `unit_id_for_inventory` from valid_inventory_unit_ids when creating an InventoryItem from a new ingredient.  
   - Document in 2.2: “User adds inventory unit information” = (A) add/edit/remove InventoryUnits in Configuration, (B) when creating an InventoryItem, unit_id comes from valid set—from user selection or same-unit rule or LLM/default.

2. **2.2 or 2.3 (minimal equivalence model)**  
   - Add to **InventoryUnit:** `base_unit_id: Optional[int] = None`, `factor_to_base: float = 1.0`.  
   - Add a small helper: `to_base_quantity(quantity, unit) -> float` (and optionally `from_base_quantity(base_quantity, unit)`).  
   - Document: “Equivalence unit” = the base unit (base_unit_id is None for that unit).  
   - Optional: seed template InventoryUnits with common equivalences (g, kg, L, ml).

3. **2.3 (normalization)**  
   - Full conversion and normalization using equivalences; RecipeUnit equivalences if needed; cross recipe ↔ inventory where appropriate.

4. **Later (optional)**  
   - Add **display_unit_id** on InventoryItem and use equivalences for display/reporting.

---

## Summary

- **Adding inventory unit information:**  
  - **Configuration:** User manages InventoryUnits (add/edit/remove) via registry; templates pre-fill.  
  - **Creating InventoryItem:** Always use a unit from valid_inventory_unit_ids—from user selection (direct add) or from same-unit / user / LLM when creating from new ingredient; require `unit_id_for_inventory` in add_ingredient flow.

- **Equivalence and equivalence unit:**  
  - **Model:** Add optional `base_unit_id` and `factor_to_base` to InventoryUnit (and later RecipeUnit); “equivalence unit” = that base unit.  
  - **Flow:** User can set base unit and factor in Configuration (or use template); use to_base_quantity/from_base_quantity for conversions; optional later: display_unit_id on InventoryItem for reporting.  
  - **Order:** Document and optionally add fields in 2.2; implement conversion logic in 2.3; add per-item display unit later if needed.

This keeps the workflow for creating inventory items coherent and ties equivalence and equivalence unit to a single, clear model and implementation order.

---

## Part 4 — Welcome onboarding: bulk upload and LLM suggestions

### 4.0 Branching by “how structured is your business?”

At the start of onboarding, the software **asks the user how structured their current business is** (e.g. “Do you already have recipes, inventory lists, or other documents?”). The answer determines the rest of the flow:

| User answer | What the software offers |
|-------------|--------------------------|
| **We have some structure** (e.g. recipes, inventory list, Excel, PDFs, photos) | **Upload path:** User uploads those documents. The system parses them and the **LLM structures** the data (units, equivalences, categories, draft recipes/items). User then **reviews and confirms** (or edits) the suggestions. |
| **We don’t have anything** (starting from zero) | **Manual path:** No upload. The system guides the user to **create everything manually**: choose a template (by restaurant type), add recipe units and inventory units step by step, define categories and families, then add recipes and inventory items as they go. |

So onboarding is **adaptive**: one initial question (“How structured is your business?”) leads either to **upload → LLM structuring → review** or to **manual/template setup**. Both paths end up writing to the same registries and data model; only the way data is created differs.

#### Example copy for the onboarding screen

**Headline (Spanish)**  
¿Qué tan estructurada está tu operación hoy?

**Headline (English)**  
How structured is your operation today?

**Subtitle / description (Spanish)**  
Así sabemos si puedes subir documentos o si prefieres crear todo desde cero.

**Subtitle (English)**  
That way we know whether you can upload documents or prefer to set everything up from scratch.

**Options (user picks one)**

| Option | Spanish label | English label | Resulting path |
|--------|----------------|---------------|----------------|
| 1 | **Ya tengo recetas, listas de inventario o documentos** (Excel, PDF, fotos de menús, etc.) | **I already have recipes, inventory lists, or documents** (Excel, PDF, photos of menus, etc.) | Upload path: show upload area; after upload → LLM structures → review. |
| 2 | **No tengo nada aún / Estoy empezando** | **I don’t have anything yet / I’m just getting started** | Manual path: no upload; show template selection (by restaurant type), then step-by-step setup. |
| 3 (optional) | **Tengo algo, pero prefiero configurar manualmente** | **I have some things, but I prefer to set up manually** | Manual path (same as 2); user can upload later from Configuration if they change their mind. |

**CTA after selection**  
- If option 1: “Subir documentos” / “Upload documents”.  
- If option 2 or 3: “Empezar con plantilla” / “Start with template” or “Configurar paso a paso” / “Set up step by step”.

**Optional follow-up (only if user chose “I have documents”)**  
Short checklist so they know what to upload: “Puedes subir: listas de recetas, inventarios en Excel, fotos de menús, listas de proveedores.” / “You can upload: recipe lists, inventory spreadsheets, menu photos, supplier lists.”

### 4.1 Idea: upload path (when the business has structure)

When the user **has** recipes, inventory lists, or other documents, they can upload them during onboarding. The system then:

1. **Ingests and parses** the documents (Alignment agent: extract text, tables, structure).
2. **Uses LLM agents** to suggest structured data: inventory units, recipe units, **unit equivalences** (e.g. “caja” → 10 kg), categories, families, and even draft recipes or inventory items.
3. **Presents suggestions** to the user for review; user confirms, edits, or rejects. Only confirmed data is written to the registries and data model.

This fits the existing design: the **Alignment agent** already handles “normalization, unit conversion, semantic unification”; onboarding bulk upload is an **input path** that feeds that agent. The **Configuration** step can then be “review and confirm what we inferred from your uploads” instead of starting from empty templates.

### 4.2 What the LLM can suggest from uploaded content

| Uploaded content | LLM can suggest |
|------------------|------------------|
| Recipe lists / menus / PDFs | Recipe names, categories, **recipe units** (g, taza, pza), ingredient names |
| Inventory / stock lists / Excel | **Inventory units** (caja, bolsa, kg, L), **equivalences** (1 caja = 10 kg), inventory item names, families |
| Supplier docs / price lists | Unit names and equivalences (e.g. “caja 10 kg”), custom unit names |
| Mixed documents | Deduplicate units, map “caja” → equivalence to kg, suggest CategoryRecipe / FamilyInventory from context |

So: **inventory unit equivalences** (including custom units like “Caja” = 10 Kilogramos) can be **suggested by the LLM** from uploaded docs, then the user confirms or edits them in the UI (see Part 5). Recipe units, categories, and families can be suggested the same way.

### 4.3 Flow (high level)

**Step 0 — One question first**  
“How structured is your business today?” (e.g. Do you have recipes? Inventory lists? Documents?)  
→ **Has structure** → go to Upload path (below).  
→ **Nothing / starting from zero** → go to Manual path (4.3b).

**Upload path (when user has structure)**  
1. **Upload:** User uploads one or more files (PDF, Excel, images, text): recipes, inventory lists, menus, supplier docs, etc.
2. **Alignment + LLM:** System parses content and runs LLM to propose: inventory units (with optional equivalence + equivalence unit), recipe units, categories, families, and optionally draft recipes/inventory items.
3. **Review screen:** User sees proposed units and equivalences (e.g. “Caja → 10 Kilogramos”); can add, edit, or remove before confirming.
4. **Confirm:** Confirmed proposals are written to InventoryUnitRegistry (and RecipeUnitRegistry, category/family registries). Equivalences are stored as `base_unit_id` + `factor_to_base` on each InventoryUnit (see Part 5).
5. **Continue:** Rest of onboarding or Configuration uses this data; later, adding ingredients or inventory items can still trigger LLM suggestions.

**Manual path (when user has nothing)**  
1. **No upload.** System offers a **template** based on restaurant type (from Classification): recipe categories, inventory families, recipe units, inventory units (templates-recipe-and-inventory).
2. User **accepts or customizes** the template (add/remove units, categories, families).
3. User then **creates recipes and inventory items manually** as they go (add recipe, add ingredient; add inventory item with unit, etc.). Optionally, LLM can still suggest things (e.g. category for a new ingredient) during day-to-day use.
4. **Continue:** Same registries and data model; data is built step by step instead of from upload.

### 4.4 Benefits

- **One question, two paths:** Users who have structure can upload and let the LLM do the heavy lifting; users who don’t aren’t stuck—they get a guided manual path (templates, step-by-step) instead of a blank upload screen.
- **Less manual setup (upload path):** Owner doesn’t type every unit and equivalence; the system proposes from their own documents.
- **Consistent vocabulary:** Units and equivalences (e.g. “Caja = 10 kg”) match how the restaurant already talks and orders.
- **Single source of truth:** Same registries (InventoryUnit, RecipeUnit, etc.) and same equivalence model whether data came from upload, template, or manual add. LLM suggestions are just a way to **populate** those registries.

---

## Part 5 — Custom inventory units with equivalences (UI → data model)

### 5.1 The UI pattern (e.g. “Caja = 10 Kilogramos”)

The UI has three fields:

| Field (Spanish)        | Meaning                    | Example   |
|------------------------|----------------------------|-----------|
| **Unidad de Inventario** | The custom inventory unit  | Caja      |
| **Equivalencia**       | Numeric factor             | 10        |
| **Equivalencia Unidad**| The reference (standard) unit | Kilogramos |

Interpretation: **1 Caja = 10 Kilogramos.** So the “custom” unit is defined by linking it to a standard unit with a quantity.

### 5.2 Mapping to the data model

There is **no separate “custom unit” type.** “Caja” is a normal **InventoryUnit** with:

- `name`: "Caja" (or "caja")
- `symbol`: e.g. "caja" or "Cja"
- **Equivalence:** `base_unit_id` = id of the unit “Kilogramos”, `factor_to_base` = 10

So: **1 unit of this InventoryUnit = 10 units of the base (Equivalencia Unidad).** That matches the UI exactly:

- **Unidad de Inventario** → the InventoryUnit being defined (e.g. Caja).
- **Equivalencia** → `factor_to_base` (e.g. 10).
- **Equivalencia Unidad** → the InventoryUnit referenced by `base_unit_id` (e.g. Kilogramos).

Standard units like Kilogramos or Gramo can have `base_unit_id = None` and `factor_to_base = 1.0` (or point to a canonical base like Gramo with factor 1000 for kg). Custom units like Caja, Bolsa, Bote always have `base_unit_id` set to a standard/reference unit and `factor_to_base` set to the number in “Equivalencia”.

### 5.3 Implementation checklist for “custom” units

- **InventoryUnit** has optional `base_unit_id: Optional[int] = None` and `factor_to_base: float = 1.0`.
- **UI (Configuration / onboarding review):**
  - **Unidad de Inventario:** Create or select an InventoryUnit (name/symbol). If it’s new (e.g. “Caja”), add it to the registry first.
  - **Equivalencia:** Numeric input → `factor_to_base`.
  - **Equivalencia Unidad:** Dropdown of existing InventoryUnits (typically “standard” ones like Kilogramos, Litro, Pieza) → `base_unit_id`.
- **Validation:** `factor_to_base > 0`; `base_unit_id in valid_inventory_unit_ids()`; no cycles (unit A’s base must not eventually point back to A).
- **Display:** When showing an equivalence, resolve `base_unit_id` to the unit’s name/symbol (e.g. “Kilogramos”) and show “1 Caja = 10 Kilogramos”.

### 5.4 How this fits with onboarding upload

1. User uploads a document that mentions “caja 10 kg” or “caja = 10 kilogramos”.
2. LLM suggests: add InventoryUnit “Caja” with equivalence 10 to “Kilogramos”.
3. On the review screen, the same three fields appear: Unidad de Inventario = Caja, Equivalencia = 10, Equivalencia Unidad = Kilogramos. User can edit and confirm.
4. System creates or updates the InventoryUnit “Caja” with `base_unit_id = id(Kilogramos)`, `factor_to_base = 10`.

So custom inventory units like “Caja” **show specific equivalences** by storing them as standard InventoryUnits with `base_unit_id` + `factor_to_base`. The UI in the photo maps directly to that model; onboarding bulk upload plus LLM can pre-fill those values for the user to confirm.
