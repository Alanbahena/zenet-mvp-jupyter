Validate the plan for: $ARGUMENTS

Follow these steps:

1. **Locate and read the plan files.**
   - Parse the argument to identify the task/subtask reference
     (e.g. "subtask 5.4", "5.4", "task 5").
   - **If the argument is a subtask:**
     - Read the parent task plan first: `.taskmaster/docs/task-<id>/plan.md`
       Use it only as background context to understand the overall goal and sequence.
     - Then read the subtask plan: `.taskmaster/docs/task-<id>/<subtask-id>/plan.md`
       This is the primary source of truth for validation.
   - **If the argument is a top-level task:**
     - Read only `.taskmaster/docs/task-<id>/plan.md`
   - If any required file does not exist, say so clearly and stop.
     Do not invent content.

2. **Cross-reference the codebase.**
   - Read every file listed under "Files to Modify / Create" in the plan.
   - For every import, class name, method name, decorator, and file path
     in the plan's code snippets: verify it exists in the codebase with
     the exact name and signature shown.
   - Check for stub comments or docstring notes (e.g. "subtask X.X extends this")
     that constrain what must be preserved vs. overwritten.
   - Check `tasks.json` to verify prior subtask dependencies are marked done.

3. **Run the validation checklist.**
   Evaluate each check. Assign one of: PASS / BLOCKER / FIX / OPEN.

   | # | Check |
   |---|-------|
   | 1 | Plan file exists at the expected path |
   | 2 | All files listed under "Files to Modify / Create" exist in the repo (for Modify) |
   | 3 | All imports in code snippets resolve to actual exported names |
   | 4 | All class names, method names, and signatures match the codebase exactly |
   | 5 | Stubs and scaffold comments identified; plan states what to preserve |
   | 6 | Prior subtask dependencies are marked done in tasks.json |
   | 7 | Required packages and env vars are listed under Dependencies |
   | 8 | "Out of scope" section is present and unambiguous |
   | 9 | Integration points defined: what this subtask receives and what it delivers |
   | 10 | Each test has a name, setup description, and concrete assertion |
   | 11 | Every non-obvious design decision has a one-sentence rationale |
   | 12 | Every checklist item is binary (verifiable as done / not done) |
   | 13 | Names in the plan are consistent with names in the codebase throughout |
   | 14 | Edge cases are handled or explicitly deferred with a location |

4. **Classify each finding using exactly three tiers:**

   **BLOCKER** — Plan cannot be implemented as written. Must resolve before starting.
   - State the problem precisely.
   - State the fix. Be specific: correct path, correct name, what to add or remove.

   **FIX** — Clear issue with an unambiguous correction. Apply before or during implementation.
   - State the problem.
   - State the fix inline. One line each.

   **OPEN** — Ambiguous or out-of-scope design gap. Does not block current work.
   Use this exact format for each:
   ```
   [OPEN] #N — Short title
   Problem:           What gap or ambiguity was found, and where.
   Impact:            What degrades or breaks if this is never addressed.
   Suggested action:  Create subtask / add note to parent plan / defer to task X.
   ```

5. **Present the results using this exact structure:**

   **Validation summary**
   X passed · Y blockers · Z fixes · W open suggestions

   **Blockers** (must resolve before implementation)
   Numbered list. Problem + fix for each. If none: write "None."

   **Fixes** (clear corrections, apply before or during implementation)
   Numbered list. Problem + fix inline for each. If none: write "None."

   **Open suggestions** (design gaps for future planning)
   One block per suggestion using the [OPEN] format above. If none: write "None."

   **Passed checks**
   Comma-separated list of check numbers that passed cleanly.

6. **Persist open suggestions to the right plan file.**
   Do this only if there are open suggestions. For each one, determine scope:

   - **Affects the next subtask directly** → append to the current subtask plan
     (`taskmaster/docs/task-<id>/<subtask-id>/plan.md`) under "Risks and Open Questions".
   - **Affects a later subtask in the same task** → append to the parent task plan
     (`.taskmaster/docs/task-<id>/plan.md`) under "Risks and Open Questions".
   - **Affects a different future task** → append to the parent task plan under
     "Risks and Open Questions" with a note naming the target task.

   Append each suggestion using this exact format (do not rewrite existing content):
   ```
   ### [OPEN] — <Short title>
   **Source:** Validation of subtask <id>
   **Problem:** <What gap or ambiguity was found, and where.>
   **Impact:** <What degrades or breaks if this is never addressed.>
   **Suggested action:** <What to do and when.>
   ```

   After writing, confirm to the user: "Persisted N open suggestion(s) to <file path(s)>."
   If there are no open suggestions, skip this step entirely.

7. Keep findings tight — one finding per issue, no walls of text.
   Do not explain concepts. This output is for the implementer and planner, not a learner.
