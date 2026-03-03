Break down the plan for: $ARGUMENTS

Follow these steps:

1. **Locate and read the plan files.**
   - Parse the argument to identify the task/subtask reference
     (e.g. "subtask 5.4", "5.4", "task 5").
   - **If the argument is a subtask:**
     - Read the parent task plan first: `.taskmaster/docs/task-<id>/plan.md`
       Use it to understand the overall goal, architectural decisions, and how
       this subtask fits in the sequence. Do not summarize it — use it as background
       context only. It surfaces in the output only when it explains something the
       subtask plan references (e.g. a deferred item, an integration point, a prior decision).
     - Then read the subtask plan: `.taskmaster/docs/task-<id>/<subtask-id>/plan.md`
       This is the primary source of truth for the breakdown.
   - **If the argument is a top-level task:**
     - Read only `.taskmaster/docs/task-<id>/plan.md`
   - If any required file does not exist, say so clearly and stop.
     Do not invent content.

2. **Cross-reference the codebase before presenting the breakdown.**
   - Read every file listed under "Files to Modify / Create" in the plan.
   - Verify that imports, class names, method signatures, decorators, and patterns
     in the plan match what actually exists in the codebase.
   - Note any scaffolding, stub comments, or forward references already present in
     the existing files that this subtask is building on (e.g. a method whose docstring
     says "subtask X.X extends this"). These signal what to preserve vs. overwrite.
   - Flag any inconsistencies found (wrong import path, non-existent method, unnecessary
     decorator, naming mismatch, contradiction with existing docstrings, etc.).

3. **Present the breakdown using this exact structure:**

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

   **Test coverage**
   Two sub-sections:
   - Mocked tests: list each test by name/description and what it validates.
   - Live tests (if any): same format, plus which env var guards the skip.

   **Out of scope**
   Bullet list of things the plan explicitly says are NOT changing.
   This is the scope boundary — anything not listed here is fair game
   for a reviewer to challenge.

   **Risks and open questions**
   Any inconsistencies found in step 2, stub comments that need resolving,
   forward references that haven't been resolved, or decisions the plan left open.
   If none found, write "None identified."

   **Deliverable checklist (condensed)**
   Copy the checklist items from the plan verbatim, grouped by file.
   Do not add or remove items.

4. Keep each section tight. Use tables and bullet points — no walls of text.
   Do not explain concepts; this is a breakdown for an implementer, not a learner.
