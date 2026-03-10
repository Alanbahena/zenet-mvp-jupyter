# Subtask 7.4 — Error handling and validation

## Context

**Parent task:** Task 7 — Bienvenida Section: Welcome Agent + Onboarding Form
**Source of truth:** `.taskmaster/docs/task-7/plan.md` §7.4

The chat error handling and form validation were originally designed to be integrated
directly into 7.3 (`_make_chat_fn` and `_make_save_fn`). All of that was implemented
in 7.3. This subtask adds one remaining gap: a `try/except` around the
`data_lake.save_entity()` calls in `_make_save_fn` to surface DB write failures as
a friendly Spanish message instead of a raw Gradio stack trace.

**Prior (7.3):** Full `bienvenida.py` with form + chat, validation, and chat error
handling already in place.

**Next (7.5):** Add `WelcomeAgent` to `core/__init__.py` re-exports and update task
status. No dependency on this subtask's specific change.

---

## What was already implemented in 7.3

| Requirement | Location | Status |
|-------------|----------|--------|
| `try/except Exception` around `agent.run()` | `_make_chat_fn` line 79 | Done |
| Friendly Spanish error reply on API failure | `_make_chat_fn` line 80 | Done |
| `agent.save_state()` called after try/except | `_make_chat_fn` line 81 | Done |
| `if not session_id` guard in `save_fn` | `_make_save_fn` line 40 | Done |
| `if not session_id` guard in `chat_fn` | `_make_chat_fn` line 67 | Done |
| User name required — Spanish error | `_make_save_fn` line 42 | Done |
| Restaurant name required — Spanish error | `_make_save_fn` line 44 | Done |
| `None` restaurant type accepted | `_make_save_fn` line 47 | Done |

---

## Remaining gap

`data_lake.save_entity()` in `_make_save_fn` is not wrapped in try/except. If the
DB write fails (disk full, DB locked, permissions error), the operator sees a raw
Gradio stack trace instead of a friendly message. In a demo context, this is the
worst possible moment for an unhandled exception — the operator just clicked
"Guardar registro" and expects confirmation.

---

## Scope

| In scope | Out of scope |
|----------|-------------|
| `try/except` around `data_lake.save_entity()` in `_make_save_fn` | `agent.load_state()` / `save_state()` error handling |
| Friendly Spanish error on DB write failure | `_load_form_context()` error handling |
| `gr.update()` (no button change) on DB error | Input length validation |
| | SQL injection / XSS (handled by parameterized queries) |

---

## Architectural Decisions

### Decision 1: Only wrap `save_entity()` calls, not load operations

**Choice:** `try/except` only around the two `data_lake.save_entity()` calls.
`load_state()`, `save_state()`, and `_load_form_context()` are not wrapped.

**Rationale:** The save action is the most visible user-triggered operation in the
form. A failure there produces a deceptive "saved" state if not caught. Load failures
are much less likely (the DB exists if a previous save succeeded) and would surface
via the chat error handler (`try/except Exception` already wraps `agent.run()`).

---

### Decision 2: Button stays enabled on DB error

**Choice:** On `except`, return `gr.update()` (no args) for the button — leaves it
in its current state.

**Rationale:** If the save failed, the operator should be able to retry. Disabling
the button on failure would lock them out. Using `gr.update()` with no args means
no change to the button.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/sections/bienvenida.py` | Modify | Wrap `save_entity()` calls in `_make_save_fn` with `try/except` |

---

## Implementation

Replace the two bare `data_lake.save_entity()` calls and the return statement in
`_make_save_fn` with:

```python
try:
    data_lake.save_entity("restaurant", entity_id, restaurant_to_dict(restaurant))
    data_lake.save_entity("user", entity_id, user_to_dict(user))
except Exception:
    return "Error al guardar el registro. Por favor, intenta de nuevo.", gr.update()

return (
    f"Registro guardado. Bienvenido, {user.name}.",
    gr.update(value="Registro guardado", interactive=False),
)
```

**Constraints:**
- The `except` clause catches `Exception` (same pattern as `_make_chat_fn`) — not a
  specific exception type, since `DataLake` may raise `OSError`, `ValueError`, or
  `sqlite3.Error` depending on the failure mode.
- `gr.update()` with no args on the error path leaves the button unchanged.
- The success path is unchanged: button disables and shows "Registro guardado".

---

## Deliverable Checklist

### `gradio_app/sections/bienvenida.py`
- [ ] `try/except Exception` wraps both `data_lake.save_entity()` calls in `_make_save_fn`
- [ ] On `except`: returns `("Error al guardar el registro. Por favor, intenta de nuevo.", gr.update())`
- [ ] On success: returns `(f"Registro guardado. Bienvenido, {user.name}.", gr.update(value="Registro guardado", interactive=False))`
- [ ] Validation guards (session_id, user name, restaurant name) remain before the try block — unchanged
- [ ] Button behavior on validation errors unchanged (`gr.update()` with no args)

---

## Verification

```bash
# Smoke test
PYTHONPATH=. uv run python -c "
from gradio_app.app import build_app
build_app()
print('OK')
"

# Manual: trigger DB error by making data/ read-only, then click Guardar registro
# → should see Spanish error message, not a stack trace
```
