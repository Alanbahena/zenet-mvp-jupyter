# CLAUDE.md — Zenet MVP 0.1

## Project Overview

**Zenet MVP 0.1** is a cognitive operational system for restaurants. It is not a traditional app — it is the foundational layer that structures, standardizes, and models restaurant operations as a base for future intelligence and automation.

The system walks restaurant operators through a pipeline of Jupyter notebooks:
`Bienvenida → Clasificación → Configuración_inicial → Alineamiento → Estructura → Manual_operativo`

---

## Environment

- **Python:** 3.13.5 (see `.python-version`)
- **Package manager:** `uv` (preferred) — do not use pip unless uv is unavailable
- **Virtual env:** `.venv/` at project root

### Key commands

```bash
# Install dependencies
uv sync

# Add a new dependency
uv add <package-name>

# Regenerate requirements.txt
uv export --no-dev -o requirements.txt

# Run tests
uv run python -m pytest tests/

# Run a specific test file
uv run python -m pytest tests/unit/test_data_model.py

# Run main entry point
uv run python main.py

# Launch Jupyter
jupyter notebook

# Run examples (PYTHONPATH required — gradio_app and core are not installed packages)
PYTHONPATH=. uv run python examples/graph_example.py
```

### Environment variables

API keys live in `.env` (never commit this file):
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`

---

## Project Structure

```
core/                    # All business logic — the cognitive core
  domain/                # Data model layer
    data_model.py        # Entities and registries (Recipe, Restaurant, InventoryItem, etc.)
    data_model_utils.py  # Format, validation, and resolution helpers
    serialization.py     # Entity ↔ dict (to_dict / from_dict pairs)
    taxonomy.py          # Ingredient / inventory / recipe hierarchies
  operations/            # Business logic layer
    normalization.py     # Unit equivalence, conversion, deduction logic
    readiness_kpis.py    # Readiness report and KPI computation
  storage/               # Persistence layer
    persistence.py       # JsonStorage, SqliteStorage, DataLake (save/load API)
    schema.py            # SQLite schema (CREATE TABLE statements)
  ai/                    # LLM integration layer
    providers.py         # LlmProvider, OpenAiProvider, ClaudeProvider, ToolRegistry
    memory.py            # ConversationMemory
    prompts.py           # Prompt engineering utilities
    utils.py             # parse_structured_output and helpers
  agents/                # Agent framework
    base_agent.py        # BaseAgent abstract class (run, validate, tool loop, memory)
    simple_agent.py      # RestaurantInfoAgent — minimal concrete agent for validation
    welcome_agent.py     # WelcomeAgent (Task 7)
    classification_agent.py  # ClassificationAgent (Task 8)
    configuration_agent.py   # ConfigurationAgent (Task 9)
    consistency_check_agent.py # ConsistencyCheckAgent (Task 9)
    utils.py             # create_agent() factory, AgentRegistry
    graph_utils.py       # BaseGraphState, make_agent_node(), build_sequential_graph()
  __init__.py            # Re-exports from all core subpackages

gradio_app/              # Gradio UI layer
  app.py                 # build_app() — gr.Blocks with 6 tabs
  session.py             # get_data_lake(), create_session()
  components.py          # render_chat_panel()
  sections/              # One file per pipeline section (Tasks 7–9 done; 10–12 stubs)
    bienvenida.py, clasificacion.py, configuracion.py,
    alineamiento.py, estructura.py, manual_operativo.py

tests/
  unit/                  # Unit tests for every core module and gradio_app session

docs/Architecture/       # Detailed architecture docs
.taskmaster/             # Task management: tasks.json, subtask plans, PRD, docs
notebooks/               # Jupyter notebooks (pipeline stages)
data/                    # raw, processed, normalized, outputs, sessions/
examples/                # quickstart.py, tortilla_example.py, graph_example.py
```

---

## Architecture & Coding Conventions

### Entities are plain Python dataclasses — no ORM

```python
@dataclass
class RecipeUnit:
    id: int
    name: str
    symbol: str
    description: Optional[str] = None
```

Use `@dataclass` with `field()` for mutable defaults. Always include type hints and docstrings on all public classes and functions.

### Registries enforce uniqueness and validation

Every entity that participates in normalization or readiness logic is registered in a corresponding `*Registry` class (e.g. `RecipeUnitRegistry`, `InventoryUnitRegistry`, `CategoryRecipeRegistry`). Registries are the canonical source of truth; validation checks against them. Never bypass registries to create entities.

### Name-based linking (Phase A)

In Phase A, readiness and deduction logic resolves links by **name** (e.g. ingredient name → inventory item name), not by foreign key. This simplifies file-based workflows. Foreign-key-style `id` linking is used within single sessions only.

### Serialization is explicit

Every entity has a pair of functions in `serialization.py`: `<entity>_to_dict(entity)` and `<entity>_from_dict(data)`. Never use `dataclasses.asdict()` directly — use the serialization functions so any custom logic (optional fields, nested objects) is applied consistently.

### Persistence through DataLake

Always use the `DataLake` abstraction (`core/storage/persistence.py`) as the unified interface. `JsonStorage` and `SqliteStorage` are backends; calling code should not depend on which backend is active.

### Unit equivalences

`InventoryUnit` has optional `base_unit_id` and `factor_to_base` (e.g. 1 Caja = 10 kg). Conversion logic lives in `normalization.py` (`to_base_quantity`, `from_base_quantity`, `convert_quantity`). Standard units (`is_standard=True`) are kg, g, L, ml, pza; contextual units (`is_standard=False`) require an equivalence.

---

## Testing

- All tests are in `tests/unit/`
- Tests use the standard `unittest` framework
- One test file per core module (e.g. `test_data_model.py`, `test_normalization.py`)
- Run the full suite with `python -m pytest tests/`
- Tests use small in-memory fixtures — no external services or files required

When writing new code, add corresponding tests in `tests/unit/`. Tests should cover normal cases, edge cases, and validation failures (e.g. negative quantities, invalid unit IDs).

---

## Task Management (TaskMaster)

Tasks and subtasks are tracked in `.taskmaster/tasks/tasks.json`.

**Task status values:** `pending`, `in-progress`, `done`, `cancelled`

**Current task status:**
| ID | Task | Status |
|----|------|--------|
| 1 | Project setup | done |
| 2 | Data model and ontology | done |
| 3 | Data persistence layer | done |
| 4 | LLM integration framework | done |
| 5 | Agent framework | done |
| 6 | Gradio UI foundation and LangGraph integration | **done** |
| 7 | Bienvenida section agent | **done** |
| 8 | Clasificación section agent | **done** |
| 9  | Configuración section agent           | **done** |
| 10 | Alineamiento section                   | pending  |
| 11 | Estructura section                     | pending  |
| 12 | Manual operativo section               | pending  |
| 13 | Gradio UI entry point (cancelled)      | cancelled |
| 14 | Notebook pipeline orchestration (cancelled) | cancelled |
| 15 | Unit and integration tests             | pending  |
| 16 | Documentation and user guide           | pending  |
| 17 | Restaurant profile enrichment          | **done** |

**Task 10** (Alineamiento) is next.

### TaskMaster docs

Each task and subtask has a plan file under `.taskmaster/docs/task-<id>/<subtask-id>/plan.md`. Always read the relevant plan before implementing a subtask. The `.taskmaster/docs/README.md` explains the conventions for adding new docs.

---

## LLM and Agent Framework (Tasks 4–5 — done)

The framework lives in `core/ai/` and `core/agents/`:

- `core/ai/providers.py` — `LlmProvider` (abstract), `OpenAiProvider`, `ClaudeProvider`, `ToolRegistry`
- `core/ai/memory.py` — `ConversationMemory` for conversation history
- `core/ai/prompts.py` — prompt engineering utilities
- `core/ai/utils.py` — `parse_structured_output` and helpers
- `core/agents/base_agent.py` — `BaseAgent` abstract class (run loop, tool calling, memory, retry)
- `core/agents/simple_agent.py` — `RestaurantInfoAgent` (minimal concrete agent)
- `core/agents/utils.py` — `create_agent()` factory, `AgentRegistry`
- `core/agents/graph_utils.py` — `BaseGraphState`, `make_agent_node()`, `build_sequential_graph()`

Default Claude models: Sonnet 4.6 (`claude-sonnet-4-6`), Opus 4.6 (`claude-opus-4-6`), Haiku 4.5 (`claude-haiku-4-5-20251001`).

Always use `create_agent(AgentClass, provider=provider, name="...")` — never instantiate agents directly.

---

## Key Constraints

- **No ORM** — plain Python dataclasses only
- **No auto-commit** — never commit changes unless explicitly asked
- **uv over pip** — always use `uv add` / `uv sync`
- **No emojis** in code or responses unless explicitly requested
- **No over-engineering** — only build what the current task requires; no speculative abstractions
- **Do not add error handling** for cases that cannot happen; trust internal registries
- **API keys in .env only** — never hardcode credentials
- **`.env` must never be committed**

---

## Architecture Documentation

Detailed docs in `docs/Architecture/`:

| Topic | File |
|-------|------|
| Entities, registries, templates | `architecture-data-model.md` |
| Equivalence, conversion, deduction | `architecture-normalization.md` |
| Ingredient/inventory/recipe hierarchies | `architecture-taxonomy.md` |
| Format, validation, resolution helpers | `architecture-data-model-utils.md` |
| Readiness report schema and KPIs | `architecture-readiness-kpis.md` |
| Storage layer (JSON/SQLite/DataLake) | `architecture-persistence.md` |
| Gradio UI and LangGraph integration | `architecture-gradio-and-langgraph.md` |
| Agent framework                        | `architecture-agent-framework.md`            |
| Bienvenida section                     | `sections/bienvenida.md`                     |
| Clasificación section                  | `sections/clasificacion.md`                  |
| Configuración section                  | `sections/configuracion.md`                  |

Project-wide references:
- `.taskmaster/docs/prd.txt` — Product Requirements Document
- `.taskmaster/docs/templates-recipe-and-inventory.md` — Standard units and templates per restaurant type
- `.taskmaster/docs/inventory-units-and-equivalences-plan.md` — Unit equivalence design
