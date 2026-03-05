# Subtask 6.1 — Install Dependencies

## Context

**Parent task (6):** Gradio UI Foundation and LangGraph Integration Pattern.

**What this subtask achieves:** Installs `gradio` and `langgraph` into the project
environment so every subsequent subtask (6.2–6.7) can import them without error.

**Prior subtask:** Task 5 completed — delivered `BaseAgent`, `AgentRegistry`,
`DataLake`, and all core modules. All are available as inputs.

**Next subtask (6.2):** Requires `import gradio as gr` to resolve.
**Subtask 6.5:** Requires `from langgraph.graph import StateGraph, END` to resolve.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `uv add gradio` | Any Python source file creation |
| `uv add langgraph` | Any function or class implementation |
| Version verification for both packages | Changes to `.env` |
| LangGraph version check for `set_entry_point()` deprecation | Changes to `uv.lock` beyond what `uv add` manages automatically |
| Updating 6.5 plan snippets if LangGraph >= 0.2 | |

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `pyproject.toml` | Modify | `gradio` and `langgraph` added as pinned dependencies via `uv add` |

No other files change in this subtask.

---

## Dependencies

- Tasks 1–5 marked done in `.taskmaster/tasks/tasks.json`
- `uv` installed and on PATH
- Virtual environment active (`.venv/` at project root)
- Neither `gradio` nor `langgraph` is currently in `pyproject.toml` — confirmed

---

## Key Design Decisions

### Use `uv add`, not pip

**Choice:** All package installation uses `uv add`.

**Rationale:** Project convention (CLAUDE.md). `uv add` pins both packages in
`pyproject.toml` and installs into `.venv` in one step. pip would install without
updating `pyproject.toml`, breaking reproducibility.

---

### Verify imports immediately after install

**Choice:** Run Python one-liners to verify each package is importable before
proceeding to the next step.

**Rationale:** Catches version conflicts or environment issues before any code is
written against these packages.

---

## Implementation Steps

1. **Install Gradio**
   ```bash
   uv add gradio
   ```

2. **Verify Gradio**
   ```bash
   python -c "import gradio as gr; _ = gr.State; _ = gr.Blocks; print(f'gradio {gr.__version__} — gr.State and gr.Blocks OK')"
   ```
   This confirms `gr.State` and `gr.Blocks` (which exposes `.load()`) are present —
   required by 6.2–6.4. If either raises `AttributeError`, the installed version is
   too old — run `uv add "gradio>=4.0"` to constrain the minimum.

3. **Install LangGraph**
   ```bash
   uv add langgraph
   ```

4. **Verify LangGraph**
   ```bash
   python -c "from langgraph.graph import StateGraph; print('ok')"
   ```

5. **Check LangGraph version**
   ```bash
   python -c "import langgraph; print(langgraph.__version__)"
   ```
   - If version **>= 0.2**: `set_entry_point()` is deprecated. Before implementing
     subtask 6.5, update both code snippets in the parent plan (section 6.5) that
     use `graph.set_entry_point(nodes[0][0])` to instead use:
     ```python
     from langgraph.graph import StateGraph, END, START
     graph.add_edge(START, nodes[0][0])
     ```
     Note the change in the architecture doc (section 5 of 6.7).
   - If version **< 0.2**: no change needed; `set_entry_point()` still works.

6. **Confirm `pyproject.toml`**
   Verify both `gradio` and `langgraph` appear under `[project] dependencies`.

---

## Test Coverage

None — this is a pure installation subtask. No unit tests.

---

## Risks and Open Questions

1. ~~**Gradio version compatibility.**~~ Resolved — gradio 6.8.0 installed; `gr.State` and `gr.Blocks` confirmed present.

2. ~~**`set_entry_point()` deprecation.**~~ Resolved — LangGraph 1.0.10 installed; both 6.5 snippets updated to `graph.add_edge(START, ...)` with `START` imported from `langgraph.graph`.

3. **`gradio/` namespace collision (encountered during execution).** The local `gradio/` directory (no `__init__.py`) acted as a Python 3.3+ namespace package, shadowing the installed `gradio`. Fix: renamed `gradio/` → `gradio_app/` before verification. All subsequent subtasks must use `gradio_app/` as the directory name.

4. **`uv run python` required for verification.** System `python` resolves to Anaconda (`/opt/anaconda3/bin/python`), not the project `.venv`. All verification and test commands in Tasks 6–16 must use `uv run python` or activate the venv explicitly.

---

## Deliverable Checklist

- [x] Install Gradio: `uv add gradio` — gradio 6.8.0
- [x] Verify: `uv run python -c "import gradio as gr; _ = gr.State; _ = gr.Blocks; print(f'gradio {gr.__version__} — gr.State and gr.Blocks OK')"` — OK
- [x] Install LangGraph: `uv add langgraph` — langgraph 1.0.10
- [x] Verify: `uv run python -c "from langgraph.graph import StateGraph, END, START; print('ok')"` — OK
- [x] LangGraph version checked (1.0.10 >= 0.2); 6.5 plan snippets updated to `add_edge(START, ...)`
- [x] Both `gradio>=6.8.0` and `langgraph>=1.0.10` appear in `pyproject.toml` under `dependencies`
