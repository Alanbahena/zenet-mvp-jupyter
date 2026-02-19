# Task Master docs — structure and conventions

This directory holds Task Master–related documentation: PRD, task/subtask plans, and project-level design docs.

## Directory layout

- **Top level:** Project-wide documents that are not tied to a single task or subtask.
- **Nested by task:** Task- and subtask-specific artifacts live under `task-<id>/<subtask-id>/`.

### Top-level (project) docs

Keep these at the root of `.taskmaster/docs/`:

- `prd.txt` — Product Requirements Document (source for parse-prd).
- `readiness-scorecard-ux.md` — Readiness scorecard UX and presentation.
- `inventory-units-and-equivalences-plan.md` — Cross-cutting plan for units and equivalences.
- `templates-recipe-and-inventory.md` — Templates for recipe and inventory.

Any document that applies to the whole product or multiple tasks should stay here.

### Nested structure (task/subtask-specific)

**Convention:** One folder per **task**, then one folder per **subtask** (or per logical group of subtasks).

```
.taskmaster/docs/
├── README.md                    ← this file
├── prd.txt
├── readiness-scorecard-ux.md
├── inventory-units-and-equivalences-plan.md
├── templates-recipe-and-inventory.md
└── task-<TASK_ID>/              e.g. task-2/
    └── <SUBTASK_ID>/            e.g. 2.1, 2.2, 2.6
        ├── plan.md              ← main implementation plan
        ├── verification.md      ← optional verification/review
        ├── review.md            ← optional review notes
        └── ...                  ← other artifacts (e.g. validation-suggestions.md)
```

**Examples:**

- Task 2, subtask 2.1: `task-2/2.1/plan.md`
- Task 2, subtask 2.2: `task-2/2.2/plan.md`, `task-2/2.2/validation-suggestions.md`, `task-2/2.2/review.md`
- Task 2, subtask 2.6: `task-2/2.6/plan.md`, `task-2/2.6/verification.md`

## Naming inside a subtask folder

- **plan.md** — Main implementation plan for the subtask.
- **verification.md** — Verification report or checklist (e.g. for a final sub-step like 2.6.6).
- **review.md** — Review notes or alignment with other docs.
- **validation-suggestions.md** — Optional breakdown of validation suggestions.
- Use short, descriptive names for any other artifact (e.g. `api-sketches.md`, `migration-notes.md`).

## For agents (AI / automation)

When **creating new** task- or subtask-specific documentation:

1. **Determine scope:** Is this document about one task/subtask or the whole project?
2. **If task/subtask-specific:** Create or use the folder `task-<TASK_ID>/<SUBTASK_ID>/` and place the file there. Use `plan.md` for the main plan; use the names above for verification, review, or validation artifacts.
3. **If project-level:** Place the file at the **top level** of `.taskmaster/docs/` (same directory as `prd.txt` and this README).
4. **References:** When linking from one doc to another in this tree, use paths relative to `.taskmaster/docs/`, e.g. `[inventory plan](inventory-units-and-equivalences-plan.md)` or `[2.2 plan](task-2/2.2/plan.md)`.

This keeps project docs easy to find and task context clear for both humans and agents.
