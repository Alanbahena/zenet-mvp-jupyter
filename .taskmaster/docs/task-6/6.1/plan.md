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

1. **Gradio version compatibility (Risk #1 from parent plan).** Gradio < 4.0 may
   lack `gr.State` or `gr.Blocks.load()`. Step 2 catches this. Fix: pin a minimum
   version with `uv add "gradio>=4.0"` if needed.

2. **`set_entry_point()` deprecation (OPEN #1 from parent plan).** LangGraph >= 0.2
   deprecates `set_entry_point()` in favour of `add_edge(START, ...)`. Step 5 resolves
   this at install time — update the plan snippets before writing any code in 6.5.

---

## Deliverable Checklist

- [ ] Install Gradio: `uv add gradio`
- [ ] Verify: `python -c "import gradio as gr; _ = gr.State; _ = gr.Blocks; print(f'gradio {gr.__version__} — gr.State and gr.Blocks OK')"` prints without error
- [ ] Install LangGraph: `uv add langgraph`
- [ ] Verify: `python -c "from langgraph.graph import StateGraph; print('ok')"`
- [ ] LangGraph version checked; 6.5 plan snippets updated if version >= 0.2
- [ ] Both `gradio` and `langgraph` appear in `pyproject.toml` under `dependencies`
