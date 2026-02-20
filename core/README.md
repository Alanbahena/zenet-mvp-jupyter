# Core

Python core of the Zenet MVP: data model, normalization, taxonomy, persistence, and readiness KPIs.

## Modules

| Module | Purpose |
|--------|---------|
| `data_model.py` | Entities, registries, templates, fixed data (Recipe, Restaurant, User, InventoryItem, etc.) |
| `data_model_utils.py` | Format, validation, resolution helpers for ingredients and deduction |
| `normalization.py` | Unit equivalence, conversion, deduction lines |
| `taxonomy.py` | Ingredient, inventory, and recipe taxonomies and relationships |
| `readiness_kpis.py` | Readiness report and KPI computation |
| `persistence.py` | **JsonStorage**, **SqliteStorage**, **DataLake** — save/load entities (dict or object API) |
| `schema.py` | SQLite schema (tables, foreign keys) used by SqliteStorage |
| `serialization.py` | Entity ↔ dict (`to_dict` / `from_dict`) for all entity types |

## Quick start (persistence)

```python
from core import DataLake, Restaurant

# JSON backend (simple, human-readable files)
lake = DataLake(data_dir="data/json")

# Or SQLite backend (one DB file, relationships)
lake = DataLake(db_path="data/app.db")

# Save/load as domain objects
restaurant = Restaurant(id=1, name="La Pizzeria", address="Calle 1", restaurant_type_id=1, notes=None)
lake.save_entity_obj(restaurant)
loaded = lake.load_entity_obj("restaurant", 1)
```

See [Persistence architecture](../docs/Architecture/architecture-persistence.md) for full API and design.

## Documentation

From project root, see `docs/Architecture/`:

- [Data model](../docs/Architecture/architecture-data-model.md)
- [Normalization](../docs/Architecture/architecture-normalization.md)
- [Taxonomy](../docs/Architecture/architecture-taxonomy.md)
- [Data model utils](../docs/Architecture/architecture-data-model-utils.md)
- [Readiness KPIs](../docs/Architecture/architecture-readiness-kpis.md)
- [**Persistence**](../docs/Architecture/architecture-persistence.md)
