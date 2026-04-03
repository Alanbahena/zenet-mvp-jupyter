# Task 18 — ngrok Demo Deployment

## Context

Final task in MVP 0.1. Exposes the local Gradio app via ngrok so the operator can run
demos from an iPad without any cloud deployment. Also wires `main.py` as the canonical
launch entry point, replacing the current placeholder.

**Current state before this task:**
- `main.py` — placeholder only: `print("Hello from mvp-jupyter!")`. Does not import or
  launch the Gradio app.
- `gradio_app/app.py` — has `if __name__ == "__main__": build_app().launch()` (localhost
  only, no `server_name`).
- `README.md` — launch command is `uv run python -m gradio_app.app` (set in Task 16).
- `CLAUDE.md` — no ngrok commands documented.
- `scripts/seed_data.py` — demo data uses "Mi Restaurante" / "Operador Demo" (generic).

---

## Scope

### In scope

1. **18.1** — Update `main.py` to import `build_app` and call `.launch(server_name='0.0.0.0', server_port=7860)`.
2. **18.2** — Document ngrok one-time setup and per-demo launch sequence in `CLAUDE.md`. Update `README.md` launch command to `uv run python main.py`.
3. **18.3** — Verify two-column Gradio layout on iPad Safari (landscape + portrait). Document findings. No code changes unless layout is unusable.
4. **18.4** — Verify `seed_data.py` produces a compelling demo scenario. Update restaurant name / operator name if needed.
5. **18.5** — Mark Task 18 done in `CLAUDE.md` and `tasks.json`.

### Out of scope

- HuggingFace Spaces or any cloud deployment.
- CSS fixes for iPad portrait layout — document only.
- Changes to `gradio_app/app.py` `if __name__` block.
- Any changes to `core/` business logic.
- New Python dependencies.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `main.py` | Modify | Import `build_app`; call `.launch(server_name="0.0.0.0", server_port=7860)` |
| `CLAUDE.md` | Modify | Add ngrok setup + per-demo launch commands under Key commands; mark task 18 done |
| `README.md` | Modify | Update launch command to `uv run python main.py` |
| `scripts/seed_data.py` | Possibly modify | Update restaurant/operator name if current values are not demo-ready |

---

## Implementation Steps

### Step 1 — `main.py`: Wire as launch entry point

Replace the entire file content:

```python
from gradio_app.app import build_app

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860)
```

`build_app` is confirmed at `gradio_app/app.py:9`.

### Step 2 — `README.md`: Update launch command

In the **Basic usage** section, change:
```bash
# Before
uv run python -m gradio_app.app

# After
uv run python main.py
```

### Step 3 — `CLAUDE.md`: Add ngrok commands under Key commands

Append to the existing `### Key commands` block:

```bash
# Launch app for external access (ngrok demo)
uv run python main.py        # Terminal 1 — starts Gradio on 0.0.0.0:7860
ngrok http 7860               # Terminal 2 — opens public tunnel; copy the https URL

# One-time ngrok setup (do once per machine)
brew install ngrok
ngrok config add-authtoken <your-token>   # token from dashboard.ngrok.com
```

### Step 4 — `scripts/seed_data.py`: Verify demo scenario

Current values:
- `RESTAURANT["name"]`: `"Mi Restaurante"`
- `USER["name"]`: `"Operador Demo"`
- `USER["email"]`: `"demo@mirestaurante.com"`
- 3 recipes, 20 inventory items, expected score B (~80)

Decision: update only the `RESTAURANT["name"]`, `USER["name"]`, and `USER["email"]`
constants if a more compelling name is chosen. Do not change entity structure, recipe
data, or inventory items — the B-score scenario must remain intact.

### Step 5 — `CLAUDE.md`: Update task status

```
| 18 | ngrok demo deployment | **done** |
```

### Step 6 — Manual verification

```
Terminal 1:  uv run python main.py
             → Gradio starts, confirm "Running on http://0.0.0.0:7860"

Terminal 2:  ngrok http 7860
             → Copy the https://xxxx.ngrok-free.app URL

iPad Safari: Open the URL in landscape mode
             → Verify 6 tabs load, chat panel responds, file upload works
             → Switch to portrait, note any layout issues (document, don't fix)
```

---

## Subtask Execution Order

18.1 must complete before 18.2 (ngrok docs reference `uv run python main.py`).
18.3 requires 18.1 to be done (needs the app running on 0.0.0.0). 18.4 and 18.5 are
independent.

```
18.1 (main.py) → 18.2 (CLAUDE.md + README) → 18.3 (iPad verify)
18.4 (seed_data verify) — independent
18.5 (status update) — last
```

---

## Test Coverage

No automated tests are warranted for a launch-config and documentation task.

Manual end-to-end verification checklist (Step 6 above) is the acceptance test:
- Gradio starts on `0.0.0.0:7860`
- ngrok tunnel is reachable from iPad Safari
- Full pipeline flow works through the tunnel (all 6 tabs, chat, file upload)
- Seed data produces a readable, B-grade manual operativo

The existing `pytest tests/` suite covers all agent and UI logic and should be run
(`uv run python -m pytest tests/ -k "not Live"`) before the demo to confirm no
regressions.

---

## Deliverable Checklist

`main.py`
- [ ] Imports `build_app` from `gradio_app.app`
- [ ] Calls `build_app().launch(server_name="0.0.0.0", server_port=7860)`

`README.md`
- [ ] Launch command updated to `uv run python main.py`

`CLAUDE.md`
- [ ] ngrok one-time setup commands added under Key commands
- [ ] Per-demo two-terminal launch sequence documented
- [ ] Task 18 status: `pending` → `done`

`scripts/seed_data.py`
- [ ] Demo scenario verified as compelling (restaurant name, operator name)
- [ ] Updated if needed (name constants only)

Verification
- [ ] `uv run python main.py` starts Gradio on `0.0.0.0:7860`
- [ ] `ngrok http 7860` tunnel opens and URL is reachable from iPad Safari
- [ ] Full demo flow works end-to-end through the tunnel
- [ ] iPad landscape layout is usable; portrait findings documented

---

## Risks and Open Questions

### [OPEN] — `gradio_app/app.py` still has a localhost-only `if __name__` block
**Problem:** After 18.1, both `main.py` (0.0.0.0:7860) and `python -m gradio_app.app`
(localhost only) launch the app, but only `main.py` is demo-safe. A developer running
the `-m` form would get a localhost-only session.
**Impact:** Demo setup confusion; accidental localhost launch before a demo.
**Suggested action:** Either remove the `if __name__` block from `app.py` (making it
import-only), or add a comment noting that `main.py` is the canonical launch path.

### [OPEN] — 4 pre-existing test failures unresolved
**Problem:** `test_welcome_agent` (2), `test_classification_agent` (1), and
`test_structuring_agent` live test (1 flaky) still fail. Flagged in task-15 and task-16
plans. Not fixed.
**Impact:** `pytest tests/` exits non-zero before the demo, which could alarm a reviewer.
**Suggested action:** Fix the `test_welcome_agent` and `test_classification_agent`
failures (appear to be DataLake session-key mismatches) before the ngrok demo, or
explicitly `@unittest.skip` them with a note explaining the known issue.
