# Task 16 — Documentation and User Guide

## Context

This task is the last deliverable before Task 18 (ngrok demo). It brings the project's
documentation up to date with the as-built codebase (Tasks 7–15 complete) so any new
developer or demo viewer can orient themselves immediately.

**Note:** The `tasks.json` details block for task 16 is obsolete. It references Sphinx,
`docs/user_guide/`, `docs/api/`, a workflow engine, and notebook orchestration — none of
which exist or are planned. The actionable scope is derived from the actual repo state.

**Current state before this task:**
- `docs/Architecture/` — complete and current (15 files, all 6 pipeline section docs included).
  No changes needed there.
- `README.md` — exists but significantly outdated (wrong tech stack, wrong commands, missing
  agents, stale test counts, Architecture table missing 6 section docs).
- `CLAUDE.md` — Tasks 12 and 15 still show `pending`; needs updating.
- `tasks.json` — Tasks 12 and 15 still `"pending"`; Task 16 already `"in-progress"`.

---

## Scope

### In scope

1. Overhaul `README.md` to accurately reflect the as-built codebase.
2. Update `CLAUDE.md` task status table: Tasks 12 and 15 → `done`.
3. Update `.taskmaster/tasks/tasks.json`: Tasks 12 and 15 → `"done"`.

### Out of scope

- `docs/user_guide/` — operator-facing guide (not planned for MVP 0.1).
- `docs/developer/` and `docs/api/` — referenced in cancelled tasks 13/14.
- Sphinx configuration — `docs/Architecture/` markdown approach is sufficient.
- `.env.example` creation — separate decision needed (see Risks).
- Fixing the 4 pre-existing test failures in `test_welcome_agent` / `test_classification_agent`.
- Any changes to `core/` or `gradio_app/` production code.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `README.md` | Modify | Fix tech stack, commands, project structure, architecture table, test counts |
| `CLAUDE.md` | Modify | Mark Tasks 12 and 15 as `done` in the status table |
| `.taskmaster/tasks/tasks.json` | Modify | Set `"status": "done"` for tasks 12 and 15 |

---

## Implementation Steps

### Step 1 — `README.md`: Fix Tech Stack section

Remove frameworks never used:
- LangChain, CrewAI, Autogen

Keep / correct:
- Claude SDK (Anthropic), LangGraph (used in `core/agents/graph_utils.py`)
- Python: `3.13.5` (not `3.10+`)
- Gradio UI, SQLite, JSON persistence

### Step 2 — `README.md`: Fix Getting Started / commands

| Current (wrong) | Correct |
|-----------------|---------|
| `python main.py` | `uv run python -m gradio_app.app` |
| No seed command | `uv run python scripts/seed_data.py` |
| No reset command | `uv run python scripts/reset_session.py && uv run python scripts/seed_data.py` |
| `uv sync --active` | `uv sync` |

Remove the reference to `cp .env.example .env` — `.env.example` does not exist (or create it;
see Risks).

### Step 3 — `README.md`: Fix Project Structure tree

Update `core/` to show the actual layout:

```
core/
  domain/
    data_model.py
    data_model_utils.py
    serialization.py
    taxonomy.py
  operations/
    normalization.py
    readiness_kpis.py
  storage/
    persistence.py
    schema.py
  ai/
    providers.py
    memory.py
    prompts.py
    utils.py
  agents/
    base_agent.py
    simple_agent.py
    welcome_agent.py
    classification_agent.py
    configuration_agent.py
    consistency_check_agent.py
    alignment_agent.py
    structuring_agent.py
    manual_operativo_agent.py
    utils.py
    graph_utils.py
  __init__.py
```

Remove stale comment `"(replaced by Tasks 7–12)"` from sections — those are the live
implementations, not stubs.

### Step 4 — `README.md`: Fix Architecture table

Add the six missing section doc rows:

| Topic | Document |
|-------|----------|
| Bienvenida section | `docs/Architecture/sections/bienvenida.md` |
| Clasificación section | `docs/Architecture/sections/clasificacion.md` |
| Configuración section | `docs/Architecture/sections/configuracion.md` |
| Alineamiento section | `docs/Architecture/sections/alineamiento.md` |
| Estructura section | `docs/Architecture/sections/estructura.md` |
| Manual Operativo section | `docs/Architecture/sections/manual_operativo.md` |

### Step 5 — `README.md`: Fix Test Coverage table

- Update total from `462` → `580` (actual post-task-15 count).
- Remove `"100% core coverage"` claim — 4 pre-existing failures exist.
- Add missing rows (approximate counts from test suite):

| Module | Tests |
|--------|-------|
| Welcome agent | ~20 |
| Classification agent | ~18 |
| Configuration agent | ~22 |
| Alignment agent | ~23 |
| Structuring agent | ~14 |
| Gradio session | ~8 |
| Readiness KPIs | 6 |
| Manual Operativo | 14 |
| Graph utils | ~12 |

### Step 6 — `CLAUDE.md`: Update task status table

```
| 12 | Manual operativo section               | **done** |
| 15 | Unit and integration tests             | **done** |
```

### Step 7 — `.taskmaster/tasks/tasks.json`: Update task statuses

Set `"status": "done"` for task ids `"12"` and `"15"`.

---

## Test Coverage

No tests needed — documentation changes have no test surface. Verification is manual
review of the rendered README (e.g. on GitHub or via `grip`).

---

## Deliverable Checklist

`README.md`
- [ ] Tech stack: LangChain / CrewAI / Autogen removed; Claude SDK, Python 3.13.5 correct
- [ ] Launch command updated to `uv run python -m gradio_app.app`
- [ ] Seed and reset commands added
- [ ] `.env.example` reference resolved (removed or file created)
- [ ] Project structure tree reflects actual `core/` layout with all agent files
- [ ] Section `"(replaced by Tasks 7–12)"` comment removed from sections listing
- [ ] Architecture table includes all 6 section docs
- [ ] Test coverage table count updated to ~580 and row list matches current test files
- [ ] `"100% core coverage"` claim removed or qualified

`CLAUDE.md`
- [ ] Task 12 status: `pending` → `done`
- [ ] Task 15 status: `pending` → `done`

`.taskmaster/tasks/tasks.json`
- [ ] Task 12: `"status": "done"`
- [ ] Task 15: `"status": "done"`

---

## Risks and Open Questions

### [OPEN] — `.env.example` does not exist
**Problem:** `README.md` currently instructs `cp .env.example .env` (line 297). The file
does not exist in the repo, so the instruction fails for a new developer.
**Impact:** Onboarding friction; demo setup fails silently.
**Suggested action:** Either create a minimal `.env.example` with placeholder values
(`ANTHROPIC_API_KEY=`, `OPENAI_API_KEY=`) before the ngrok demo (Task 18), or replace
the copy instruction with "Create a `.env` file in the project root with the following keys."

### [OPEN] — 4 pre-existing test failures before ngrok demo
**Problem:** `test_welcome_agent` (2 failures) and `test_classification_agent` (1 failure)
and `test_structuring_agent` live test (1 flaky failure) remain from before task 15.
**Impact:** `pytest tests/` exits non-zero, which could alarm a demo viewer or CI run.
**Suggested action:** Investigate and fix before Task 18, or mark the live structuring test
as `@unittest.skip` if it is consistently flaky. Add a note to Task 18 plan.

### [OPEN] — README launch command will become stale after Task 18
**Source:** Validation of task 16
**Problem:** Step 2 sets the launch command to `uv run python -m gradio_app.app`. Task 18 (subtask 18.1) will update `main.py` to call `build_app().launch(server_name='0.0.0.0', server_port=7860)`, making `uv run python main.py` the canonical demo command. If Task 16 writes the `-m` flag form, Task 18 needs a second README touch.
**Impact:** README launch command is accurate after Task 16 but stale after Task 18 unless Task 18 explicitly updates it again.
**Suggested action:** Defer the launch command update to Task 18, which owns `main.py`. Task 16 can update everything else in README and leave a `# TODO: update after Task 18` note on the launch line, or write `uv run python main.py` now and note Task 18 will wire `main.py` properly.
