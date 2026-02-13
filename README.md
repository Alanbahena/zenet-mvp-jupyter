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

## 📁 Project Structure

```txt
zenet_mvp_0_1/
│
├── notebooks/
│   ├── 00_context.ipynb
│   ├── 01_ingestion.ipynb
│   ├── 02_normalization.ipynb
│   ├── 03_ontology_mapping.ipynb
│   ├── 04_agents.ipynb
│   ├── 05_workflows.ipynb
│   ├── 06_reasoning.ipynb
│   ├── 07_decisions.ipynb
│   └── 08_gradio_interface.ipynb
│
├── gradio/
│   └── app.py
│
├── core/
│   ├── agents/
│   ├── workflows/
│   ├── models/
│   ├── ontology/
│   ├── engine/
│   └── utils/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── normalized/
│   └── outputs/
│
└── main.py
