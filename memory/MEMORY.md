# Zenet MVP 0.1 — Project Memory

## Project
Cognitive operational system for restaurants. Foundational layer (not a SaaS/app).
Python 3.13.5 | uv package manager | `.venv/` | OpenAI + Anthropic APIs in `.env`.

## Key files
- `core/` — all business logic (data_model, normalization, taxonomy, persistence, serialization, readiness_kpis)
- `core/__init__.py` — re-exports everything from all core modules
- `CLAUDE.md` — full project guide for Claude (created 2026-02-20)
- `.taskmaster/tasks/tasks.json` — all 16 project tasks
- `docs/Architecture/` — detailed architecture docs

## Task status (as of 2026-02-20)
- Tasks 1–3: done (project setup, data model, persistence)
- Task 4: **in-progress** — LLM integration framework (`core/llm_framework.py` to be created)
- Tasks 5–16: pending (agents, workflow engine, notebooks, UI, tests, docs)

## Conventions
- Plain Python dataclasses (no ORM)
- Registries enforce uniqueness/validation
- Name-based linking in Phase A (not foreign keys)
- Explicit serialization via `*_to_dict` / `*_from_dict` in `serialization.py`
- Always use `DataLake` abstraction, not raw JsonStorage/SqliteStorage
- Tests in `tests/unit/`, one file per core module, standard unittest

## Memory files
- [project_task11_standard_units.md](project_task11_standard_units.md) — Task 11 must hardcode standard unit chains before deduction logic
- [project_task11_vision.md](project_task11_vision.md) — Task 11 vision: inventory structuring via chat/file upload, building on Alineamiento base inventory

## Preferences
- Use `uv` (never pip unless uv unavailable)
- No emojis
- No auto-commits
- Default Claude model: claude-sonnet-4-6
