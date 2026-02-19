# Implementation plan: Subtask 2.1 — Core entity classes in `data_model.py`

## Goal

Implement in `core/data_model.py` the nine entity classes with attributes, `__init__`, type hints, docstrings, and the Recipe–Ingredient relationship. No validation or relationship methods yet (those are 2.2).

---

## 1. Technology choice

- **Use `dataclasses`** (stdlib, Python 3.13+) for all entities: clear attributes, less boilerplate, easy to extend later with validation (2.2) or Pydantic if needed.
- **Single file**: `core/data_model.py`. No persistence or DB in 2.1.

---

## 2. Implementation order (by dependency)

Define classes in this order so that references (e.g. `unit_id`, `category_id`) are conceptually clear. No circular imports.

| Step | Class             | Depends on              | Purpose |
|------|-------------------|-------------------------|---------|
| 1    | `RecipeUnit`      | —                       | Units for recipe ingredients (e.g. g, kg, pza) |
| 2    | `InventoryUnit`   | —                       | Units for inventory (e.g. kg, L, caja) |
| 3    | `CategoryRecipe`  | —                       | Grouping of recipes (e.g. desayuno, comida, cena, bebidas) |
| 4    | `FamilyInventory` | —                       | Grouping of inventory items (e.g. "Lácteos", "Granos") |
| 5    | `InventoryCategory` | —                     | Category for perishability (e.g. perecedero, no perecedero) |
| 6    | `Restaurant`      | —                       | Top-level entity; basic restaurant info |
| 7    | `InventoryItem`   | InventoryUnit (id), InventoryCategory (category_id), optional FamilyInventory (family_id) | One inventory item; unit_id; category_id; family_id (optional) |
| 8    | `Ingredient`      | RecipeUnit (id), optional InventoryItem (id) | One ingredient in a recipe; quantity + unit_id, optional inventory_item_id |
| 9    | `Recipe`          | CategoryRecipe (id), list of Ingredient | Recipe with name, description, steps, category_id, ingredients |

---

## 3. Attributes per class

- **RecipeUnit**: `id`, `name`, `symbol` (e.g. `"g"`, `"pza"`). Optional: `description`.
- **InventoryUnit**: `id`, `name`, `symbol`. Optional: `description`.
- **CategoryRecipe**: `id`, `name`. Optional: `description`. Examples: desayuno, comida, cena, bebidas.
- **FamilyInventory**: `id`, `name`. Optional: `description`.
- **InventoryCategory**: `id`, `name`. Optional: `description`. Examples: perecedero, no perecedero.
- **Restaurant**: `id`, `name`. Optional: `address`, `restaurant_type`, `notes`.
- **InventoryItem**: Depends on **InventoryUnit** (unit of measure) and **InventoryCategory**. `id`, `name`, `unit_id`, `category_id` (references InventoryCategory — e.g. perecedero, no perecedero). Optional: `family_id` (references FamilyInventory), `description`.
- **Ingredient**: `name`, `quantity` (float), `unit_id`. Optional: `inventory_item_id`. (No `id` in 2.1 unless we want it for persistence; task example has no id.)
- **Recipe**: `name`, `description`, `steps` (list[str]), `category_id`, `ingredients` (list of `Ingredient`). Optional: `id` for persistence.

Use `field(default_factory=list)` for `Recipe.ingredients` so each recipe gets its own list.

---

## 4. Type hints and docstrings

- **Module docstring**: One paragraph describing the module (core entities for recipes, inventory, units, categories).
- **Every class**: Short docstring (one or two lines) describing the entity.
- **Every attribute**: Type (e.g. `id: int`, `name: str`, `quantity: float`, `ingredients: list[Ingredient]`). Use `| None` or `Optional` for optional refs; optional ids can be `int | None`.

---

## 5. Recipe–Ingredient relationship (as in task)

- **Recipe** has:
  - `category_id: int` (references CategoryRecipe.id)
  - `ingredients: list[Ingredient]` (default empty list)
- **Ingredient** has:
  - `name: str`, `quantity: float`, `unit_id: int` (references RecipeUnit.id)
  - `inventory_item_id: int | None` (optional reference to InventoryItem.id)

No `add_ingredient`/`remove_ingredient` in 2.1; that belongs to 2.2. Here we only ensure that a `Recipe` can be constructed with `ingredients=[...]` and that type hints are correct.

---

## 5b. Workflow: when an InventoryItem is created

**Behavior:** When an ingredient is added to a recipe and it is **new** (not already in inventory), it is added to the inventory as an **InventoryItem**. The **category_id** (perecedero / no perecedero) for that InventoryItem is **defined by the LLM model**.

1. Recipes are defined and ingredients are added to them (each ingredient has name, quantity, unit_id, and optionally later links to an InventoryItem).
2. When an ingredient is added to a recipe:
   - If the ingredient is **new** (not already present in inventory), the system creates a corresponding **InventoryItem** and adds it to inventory (with unit of measure, optional family, and **category_id**).
   - **category_id** (InventoryCategory: perecedero or no perecedero) is **determined by the LLM** — the agent or structuring flow calls the LLM to classify the ingredient as perishable or non-perishable, then uses the returned category_id when creating the InventoryItem.
   - If the ingredient already exists in inventory, link to the existing InventoryItem via `inventory_item_id`.
3. The Ingredient references the InventoryItem via `inventory_item_id`. Flow: **add ingredient to recipe → if new, LLM determines perecedero/no perecedero → create InventoryItem with that category_id and add to inventory → link ingredient**.

In 2.1 we only define the entity classes and the relationship (Ingredient has optional `inventory_item_id`). The actual logic (new vs existing, LLM call, create/link) belongs in a later subtask (e.g. 2.2 or structuring flow).

---

## 6. Conventions

- **IDs**: Use `id` for entities that are referenced elsewhere (Restaurant, Recipe, CategoryRecipe, FamilyInventory, RecipeUnit, InventoryUnit, InventoryItem). Ingredient can stay without `id` for 2.1.
- **Immutability**: Prefer `@dataclass(frozen=False)` for now so lists like `ingredients` can be mutated if needed; 2.2 can add validation.
- **Exports**: In `core/__init__.py`, export the nine classes from `data_model` so `from core import Recipe, Ingredient, InventoryCategory, ...` works.

---

## 7. Checklist before marking 2.1 done

- [ ] `core/data_model.py` exists with all 9 classes (including InventoryCategory).
- [ ] Each class has typed attributes and a docstring.
- [ ] `Recipe` has `category_id` and `ingredients: list[Ingredient]`.
- [ ] `Ingredient` has `name`, `quantity`, `unit_id`, `inventory_item_id` (optional).
- [ ] `InventoryItem` depends on InventoryUnit (unit_id) and InventoryCategory (category_id); has optional `family_id`.
- [ ] `InventoryCategory` exists with examples perecedero, no perecedero.
- [ ] Unit tests: instantiate each entity with required (and optional) attributes; create a `Recipe` with a non-empty `ingredients` list and assert counts/attributes.

---

## 8. Optional (if time)

- Add `__repr__` for easier debugging (dataclasses provide this by default).
- Use `typing.NamedTuple` for tiny value objects; for consistency, keeping all as dataclasses is fine.
