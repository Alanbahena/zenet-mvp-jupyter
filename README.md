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

## 📚 Where to read more

| Topic | Document |
|-------|----------|
| Data model (entities, registries, templates, workflows) | [architecture-data-model.md](docs/Architecture/architecture-data-model.md) |
| Normalization (equivalence, conversion, deduction) | [architecture-normalization.md](docs/Architecture/architecture-normalization.md) |
| Taxonomy (ingredient, inventory, recipe hierarchies) | [architecture-taxonomy.md](docs/Architecture/architecture-taxonomy.md) |
| Data model helpers (format, validation, resolution) | [architecture-data-model-utils.md](docs/Architecture/architecture-data-model-utils.md) |
| Readiness report (schema, KPIs, recommendations) | [architecture-readiness-kpis.md](docs/Architecture/architecture-readiness-kpis.md) |

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
│   ├── normalization.py    # Equivalence, conversion, deduction
│   ├── taxonomy.py         # Ingredient / inventory / recipe taxonomies
│   ├── data_model_utils.py # Format, validation, resolution helpers
│   └── readiness_kpis.py   # Readiness report and KPI computation
│
├── docs/
│   └── Architecture/       # architecture-data-model, normalization, taxonomy, etc.
│
├── .taskmaster/
│   └── docs/               # Task plans: README (conventions), project-level docs, task-2/2.x/ (plans, outline)
│
├── tests/
│   └── unit/               # test_data_model, test_normalization, test_taxonomy, test_data_model_utils, test_readiness_kpis
│
├── notebooks/              # Jupyter notebooks (context, ingestion, normalization, etc.)
├── gradio/                 # Gradio UI (e.g. app.py)
├── data/                   # raw, processed, normalized, outputs
├── main.py
└── README.md
```
