# Zenet — MVP 0.1  
## Cognitive Operational System for Restaurants  
**Jupyter + Gradio + Python Development Environment**

Zenet MVP 0.1 is not a traditional application.  
It is a **cognitive operational system** designed to structure, standardize, and model restaurant operations as a foundation for future intelligence and automation.

This repository represents the **foundational cognitive layer** of Zenet.

---

## 🎯 Purpose

Build the **cognitive-operational core** of Zenet:

- Organize chaotic data  
- Standardize operational structures  
- Normalize information  
- Build operational models  
- Create a scalable foundation for future automation  

> This is not a product.  
> This is not an app.  
> This is not a SaaS.  
> It is a **foundational operating system layer**.

---

## 🧠 Core Principles

- Data-first  
- Agent-first  
- Workflow-first  
- Ontology-first  
- Schema-first  
- Intelligence-first  
- Modular design  
- Scalability  
- Extensibility  

---

## 🧱 Tech Stack

### Language
- Python 3.10+

### Prototyping
- Jupyter Notebooks

### UI Layer (temporary)
- Gradio UI

### LLM & AI Frameworks
- LangChain  
- LangGraph  
- CrewAI  
- OpenAI SDK  
- Claude AI SDK  
- Autogen  

### Orchestration
- Custom workflow engine

### Persistence
- JSON  
- SQLite  

### Data Architecture
- Local data lake  
- Structured data pipelines  

---

## 🚀 Getting Started

### Requirements

- **Python** 3.13+ (see `.python-version` in the project root)
- **uv** (recommended) or pip for dependency management

### Environment setup

1. **Clone the repository** and go to the project root.

2. **Create and activate the virtual environment.**

   With **uv**:
   ```bash
   uv venv zenet-mvp
   source zenet-mvp/bin/activate   # Linux/macOS
   # zenet-mvp\Scripts\activate    # Windows
   ```

   With **Python**:
   ```bash
   python -m venv zenet-mvp
   source zenet-mvp/bin/activate   # Linux/macOS
   # zenet-mvp\Scripts\activate    # Windows
   ```

   Your prompt should show `(zenet-mvp)` when the environment is active.

3. **Install dependencies.**

   With **uv** (from project root):
   ```bash
   uv sync
   ```
   Or to install into an already-active env: `uv sync --active`.

   With **pip**:
   ```bash
   pip install -e .
   ```
   Or install from a locked list: `pip install -r requirements.txt`.

4. **Environment variables.**  
   Copy or create a `.env` file in the project root for API keys (e.g. `OPENAI_API_KEY`). Do not commit `.env`.

### Basic usage

- **Run the main script:**
  ```bash
  python main.py
  ```

- **Start Jupyter** (for notebooks):
  ```bash
  jupyter notebook
  ```
  Open notebooks from the `notebooks/` directory.

- **Gradio UI** (when implemented):
  ```bash
  python gradio/app.py
  ```
  Or from the project root: `gradio run gradio/app.py`.

### Development workflow

- Add dependencies with **uv**: `uv add <package-name>` (updates `pyproject.toml` and installs into the env).
- Regenerate **requirements.txt**: `uv export --no-dev -o requirements.txt`.
- Deactivate the environment when done: `deactivate`.

---

## 📐 Data model overview

The cognitive core is built around **entities**, **registries**, **templates**, and **fixed data**:

- **Entities:** `Recipe`, `Ingredient`, `InventoryItem`, and related types (e.g. deduction items, conversion rules) are defined as dataclasses in `core/data_model.py`. They are validated and resolved via registries.
- **Registries:** Central registries hold canonical entities (ingredients, inventory categories, recipes, restaurant types, equivalence rules). They support validation, lookup, and name-based linking used for Phase A readiness.
- **Templates:** Recipe and inventory templates are provided **per restaurant type** (e.g. fast-casual, full-service), so operational models can be tailored by segment.
- **Fixed data:** Enums and reference data such as `RestaurantType` and `InventoryCategory` anchor the model and appear in templates and validation.

---

## 🔧 Design decisions

- **Dataclasses:** Entities are plain Python dataclasses for clarity, serialization, and type hints; no ORM.
- **Registries for validation:** All entities that participate in readiness or normalization are registered; registries enforce uniqueness and support resolution by name.
- **Template-by-restaurant-type:** Templates (recipes, inventory) are keyed by `RestaurantType` so the system can scale to multiple segments without mixing templates.
- **Name-based linking (Phase A):** Readiness and deduction logic use **name-based** links (e.g. ingredient name, category name) rather than foreign keys, simplifying Phase A integration and file-based workflows.

---

## 📚 Architecture Documentation

See `docs/Architecture/` for detailed documentation:

| Topic | Document |
|-------|----------|
| Data model (entities, registries, templates, workflows) | [architecture-data-model.md](docs/Architecture/architecture-data-model.md) |
| Normalization (equivalence, conversion, deduction) | [architecture-normalization.md](docs/Architecture/architecture-normalization.md) |
| Taxonomy (ingredient, inventory, recipe hierarchies) | [architecture-taxonomy.md](docs/Architecture/architecture-taxonomy.md) |
| Data model helpers (format, validation, resolution) | [architecture-data-model-utils.md](docs/Architecture/architecture-data-model-utils.md) |
| Readiness report (schema, KPIs, recommendations) | [architecture-readiness-kpis.md](docs/Architecture/architecture-readiness-kpis.md) |
| **Persistence (storage layer, JSON/SQLite, DataLake API)** | **[architecture-persistence.md](docs/Architecture/architecture-persistence.md)** |

---

## 📋 Task Master docs (task plans and scope)

Task and subtask plans live under `.taskmaster/docs/` in a **nested structure**:

- **Top level:** Project-wide docs (e.g. `prd.txt`, `readiness-scorecard-ux.md`, `inventory-units-and-equivalences-plan.md`, `templates-recipe-and-inventory.md`).
- **By task:** Task- and subtask-specific artifacts under `task-<id>/<subtask-id>/` (e.g. `task-2/2.1/plan.md`, `task-2/2.6/verification.md`).

**Task 2 (data model and ontology)** has a single outline of all subtasks with description and scope:

| Document | Purpose |
|----------|---------|
| [.taskmaster/docs/README.md](.taskmaster/docs/README.md) | Conventions: where to put project vs task-specific docs; for agents creating new files. |
| [.taskmaster/docs/task-2/subtasks-outline.md](.taskmaster/docs/task-2/subtasks-outline.md) | Task 2 subtasks 2.1–2.7: short description and in/out scope; links to each subtask plan. |

Full implementation details for each subtask are in `task-2/<subtask-id>/plan.md` (e.g. `task-2/2.3/plan.md` for normalization).

---

## 📁 Project Structure

```txt
MVP Jupyter/
│
├── core/
│   ├── __init__.py
│   ├── data_model.py        # Entities, registries, templates
│   ├── data_model_utils.py  # Format, validation, resolution helpers
│   ├── normalization.py     # Equivalence, conversion, deduction
│   ├── taxonomy.py          # Ingredient / inventory / recipe taxonomies
│   ├── readiness_kpis.py    # Readiness report and KPI computation
│   ├── persistence.py       # JsonStorage, SqliteStorage, DataLake (save/load)
│   ├── schema.py            # SQLite schema (tables, FKs)
│   └── serialization.py     # Entity ↔ dict (to_dict / from_dict)
│
├── docs/
│   └── Architecture/        # architecture-data-model, normalization, taxonomy, persistence, etc.
│
├── .taskmaster/
│   └── docs/                # Task plans: README (conventions), project-level docs, task-2/2.x/, task-3/3.x/
│
├── tests/
│   └── unit/                # test_data_model, test_normalization, test_taxonomy, test_persistence, test_serialization, etc.
│
├── notebooks/               # Jupyter notebooks (context, ingestion, normalization, etc.)
├── gradio/                  # Gradio UI (e.g. app.py)
├── data/                    # raw, processed, normalized, outputs
├── main.py
└── README.md
```

---

## 🧪 Testing

Zenet includes comprehensive test coverage for all core modules and LLM integrations.

### Unit Tests (Mocked, No API Calls)

Unit tests use mocked API responses and run quickly without requiring API keys:

```bash
# Run all unit tests (394 tests)
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/test_data_model.py -v

# Run tests for a specific module
python -m pytest tests/unit/test_llm_framework.py -v

# Skip live tests explicitly
python -m pytest tests/unit/ -k "not Live" -v
```

### Live Integration Tests (Real API Calls)

Live tests make **real API calls** to OpenAI and Anthropic. They are **optional** and require:
1. API keys in your `.env` file
2. Active internet connection
3. Small cost per run (~$0.01 with default lightweight models)

#### Setup for Live Tests

1. **Copy `.env.example` to `.env`** (if you haven't already):
   ```bash
   cp .env.example .env
   ```

2. **Add your API keys** to `.env`:
   ```bash
   OPENAI_API_KEY=sk-your-openai-key-here
   ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
   ```

3. **(Optional) Override test models** in `.env`:
   ```bash
   # Defaults are lightweight models (recommended for cost savings)
   TEST_OPENAI_MODEL=gpt-4o-mini
   TEST_ANTHROPIC_MODEL=claude-haiku-4-5-20251001
   ```

#### Running Live Tests

```bash
# Run only live tests (requires API keys)
python -m pytest tests/unit/ -k Live -v

# Run all tests (live tests run if API keys present, skip otherwise)
python -m pytest tests/unit/ -v

# Run OpenAI live tests only
python -m pytest tests/unit/ -k LiveOpenAi -v

# Run Claude live tests only
python -m pytest tests/unit/ -k LiveClaude -v

# Run cross-provider tests
python -m pytest tests/unit/ -k LiveProviderComparison -v
```

#### One-Time Model Override

Test with production models without editing `.env`:

```bash
# Test OpenAI with gpt-4o (production model)
TEST_OPENAI_MODEL=gpt-4o python -m pytest tests/unit/ -k LiveOpenAi -v

# Test Claude with sonnet (production model)
TEST_ANTHROPIC_MODEL=claude-sonnet-4-5 python -m pytest tests/unit/ -k LiveClaude -v
```

#### Cost Considerations

**With default lightweight models:**
- Cost per full live test run: **~$0.01**
- Safe to run frequently during development
- Models used:
  - OpenAI: `gpt-4o-mini` ($0.15/$0.60 per 1M tokens)
  - Anthropic: `claude-haiku-4-5-20251001` ($0.80/$4.00 per 1M tokens)

**With production models:**
- Cost per full live test run: ~$0.05
- Only use when validating production parity
- Models:
  - OpenAI: `gpt-4o` ($2.50/$10.00 per 1M tokens)
  - Anthropic: `claude-sonnet-4-5` ($3.00/$15.00 per 1M tokens)

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Data Model | 88 | Entities, registries, templates |
| Normalization | 54 | Unit conversion, deduction logic |
| Taxonomy | 18 | Hierarchies and relationships |
| Data Model Utils | 42 | Validation, resolution, formatting |
| Persistence | 42 | JSON/SQLite storage, DataLake |
| Serialization | 70 | Entity ↔ dict conversion |
| LLM Framework | 29 | Providers, tools, prompts (mocked) |
| LLM Utils | 8 | Structured output parsing |
| Prompts | 7 | Template rendering |
| Memory | 33 | Conversation memory |
| **Live Tests** | **13** | **Real API integration** |
| **Total** | **407** | **100% core coverage** |

