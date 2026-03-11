Break down the plan for: $ARGUMENTS

Follow these steps:

1. **Locate and read the plan files.**
   - Parse the argument to identify the task/subtask reference
     (e.g. "subtask 5.4", "5.4", "task 5").
   - **If the argument is a subtask:**
     - Read the parent task plan first: `.taskmaster/docs/task-<id>/plan.md`
       Use it as background context only — do not summarize it in the output.
     - Then read the subtask plan: `.taskmaster/docs/task-<id>/<subtask-id>/plan.md`
       This is the primary source of truth for the breakdown.
   - **If the argument is a top-level task:**
     - Read `.taskmaster/docs/task-<id>/plan.md`
   - **If the plan file does not exist in `.taskmaster/docs/`:**
     - Check if a plan was drafted in the current session (e.g. in the Claude plans
       directory). If found, use it as the source of truth and note that it has not
       yet been written to `.taskmaster/docs/`.
     - If no plan exists anywhere, say so clearly and stop. Do not invent content.

2. **Cross-reference the codebase before presenting the breakdown.**
   - Read every file listed under "Files to Modify / Create" in the plan.
   - Verify that imports, class names, method signatures, decorators, and patterns
     in the plan match what actually exists in the codebase.
   - Note any scaffolding, stub comments, or forward references already present in
     the existing files that this subtask is building on. These signal what to
     preserve vs. overwrite.
   - Flag any inconsistencies (wrong import path, non-existent method, naming
     mismatch, contradiction with existing docstrings, etc.).

3. **Check plan completeness before presenting the breakdown.**
   After reading the plan and codebase, briefly verify whether the plan covers:
   - [ ] Unit tests (mocked, offline)
   - [ ] Live/integration tests (if the feature touches an external API)
   - [ ] Error handling at system boundaries (API calls, disk I/O)
   - [ ] Re-exports or public API updates (if new classes/functions are added)
   - [ ] Status updates (task tracker, CLAUDE.md, or equivalent)
   - [ ] Documentation (plan.md, architecture docs, or inline docstrings)

   If any category is absent and seems warranted, flag it in **Risks and open
   questions** — do not silently skip it. Do not add subtasks to the plan
   without the user's approval.

4. **Present the breakdown using this exact structure:**

   **Goal**
   One sentence: what this task/subtask achieves and why it matters in the sequence.
   Then two lines (from the parent plan context):
   - What the immediately prior subtask delivered that this one builds on.
   - What the immediately following subtask will need from this one.

   **What changes**
   A table: file path | action (Create / Modify) | one-line summary of the change.
   List only files explicitly named in the plan.

   **Dependencies**
   Bullet list of what must already be true before implementation begins
   (prior subtasks completed, packages installed, env vars set, etc.).

   **Key design decisions**
   For each decision in the plan: the choice made and the one-sentence rationale.
   Do not editorialize — report what the plan says.

   **Implementation steps**
   Numbered list in execution order. For each step: what file is touched, what is
   added or changed, and any specific constraints the plan calls out (field placement,
   decorator rules, backwards-compatibility notes, method ordering, etc.).

   **Subtask execution order**
   If this is a top-level task with multiple subtasks, show the dependency chain:
   e.g. `7.1 → 7.2 → 7.3 (depends on 7.1 and 7.2) → 7.4 → 7.5`
   If subtasks are independent (can run in parallel), note that explicitly.
   Omit this section for single subtask breakdowns.

   **Test coverage**
   Two sub-sections:
   - Mocked tests: list each test by name/description and what it validates.
   - Live tests: list each test, what it validates, and which env var guards the
     skip (e.g. `ANTHROPIC_API_KEY`). If no live tests exist in the plan, note
     whether they should be considered given the feature's external dependencies.

   **Out of scope**
   Bullet list of things the plan explicitly says are NOT changing.
   This is the scope boundary — anything not listed here is fair game
   for a reviewer to challenge.

   **Risks and open questions**
   Any inconsistencies found in step 2, missing plan completeness items from step 3,
   stub comments that need resolving, forward references not yet resolved, or
   decisions the plan left open.
   If none found, write "None identified."

   **Deliverable checklist (condensed)**
   Copy the checklist items from the plan verbatim, grouped by file.
   Do not add or remove items.

5. Keep each section tight. Use tables and bullet points — no walls of text.
   Do not explain concepts; this is a breakdown for an implementer, not a learner.
