# Subtask 8.3 — Draft Preview Component

## Context

Adds `render_draft_preview()` to `gradio_app/components.py`. Renders the diagnosed
standardization level as human-readable Markdown with a contextual description and a
Confirm button. Reusable by Tasks 9–12 for their own confirm flows.

**Prior:** 8.2 delivered `classification` persistence — `DataLake.save_entity("classification", ...)` is live.

**Next:** 8.4 imports `render_draft_preview`, passes its own `draft` state and `confirm_fn`,
and wires the returned button's `.click()` to a status output.

---

## Files to Modify

| File | Action | Summary |
|------|--------|---------|
| `gradio_app/components.py` | Modify | Add `_format_draft()` helper + `render_draft_preview()` function |

---

## Dependencies

- `gradio_app/components.py` exists — function is appended after `render_chat_panel`
- `gradio` (`gr`) and `typing.Callable` already imported in the file
- No new packages required
- Can run in parallel with 8.2 (no dependency between them)

---

## Design Decisions

### Decision 1: `gr.Markdown` not `gr.JSON`

Renders the draft as a human-readable Markdown block.
`gr.JSON` shows a raw dict tree — not suitable for a non-technical restaurant operator.

### Decision 2: Contextual level description (current level only)

When a level is diagnosed, show both the level label and a one-line description of
what Zenet will do next. Only the diagnosed level is shown — not all three.
Rationale: showing all three levels adds noise; the operator only needs to understand
what their specific level means when confirming.

### Decision 3: Draft re-render via `draft.change()`

`draft.change(fn=_format_draft, inputs=[draft], outputs=[markdown, confirm_btn])`
fires automatically whenever `chat_fn` returns an updated draft state — no manual
trigger needed in 8.4.

### Decision 4: Confirm button starts disabled

`gr.Button(interactive=False)` — enabled only once `standardization_level` is set
in the draft. `_format_draft` returns `gr.update(interactive=True/False)` for the button.

### Decision 5: `confirm_btn.click()` wired inside with empty outputs

`confirm_btn.click(fn=confirm_fn, inputs=[draft, session_id], outputs=[])`
The caller (8.4) chains `.then()` for any status message or additional outputs.
Avoids `render_draft_preview` needing to know 8.4's output components.

### Decision 6: `confirm_fn` signature is `(draft_dict: dict, session_id: str) -> str`

`draft` and `session_id` are the two `gr.State` inputs. `confirm_fn` receives their
values (not the State components). Returns a string status message consumed by 8.4.

---

## Implementation Steps

### 1. Module-level constants

Add after the imports in `components.py`:

```python
_LEVEL_LABELS = {
    1: "Nivel 1 — Operación en la cabeza",
    2: "Nivel 2 — Parcialmente documentado",
    3: "Nivel 3 — Operación estructurada",
}
_LEVEL_DESCRIPTIONS = {
    1: "Zenet construirá todo desde plantillas base y te guiará en cada paso.",
    2: "Zenet usará lo que tengas y complementará con plantillas donde falte.",
    3: "Zenet importará y normalizará la información existente.",
}
_DRAFT_PLACEHOLDER = "El asistente irá completando esta sección durante la conversación."
```

### 2. `_format_draft(draft: dict) -> tuple[str, dict]` helper

Pure function — no Gradio side effects. Returns `(markdown_str, gr.update(...))`.

Logic:
- If `draft` is falsy or `draft.get("standardization_level")` is `None`:
  → return `(_DRAFT_PLACEHOLDER, gr.update(interactive=False))`
- Otherwise build Markdown:
  ```
  **Nivel 2 — Parcialmente documentado**
  Zenet usará lo que tengas y complementará con plantillas donde falte.
  ```
- Return `(markdown_str, gr.update(interactive=True))`

### 3. `render_draft_preview()` function

Add after `render_chat_panel` in `components.py`:

```python
def render_draft_preview(
    draft: gr.State,
    confirm_fn: Callable,
    session_id: gr.State,
) -> gr.Button:
    """
    Render the right-column draft preview panel inside an active gr.Column context.

    Renders: gr.Markdown (live classification draft) + Confirm gr.Button.
    The Markdown re-renders automatically whenever the draft gr.State changes.
    The Confirm button is disabled until standardization_level is set in the draft.

    draft: gr.State holding the current classification draft dict
           (keys: standardization_level).
    confirm_fn signature: (draft_dict: dict, session_id: str) -> str
      - receives the draft dict and session_id values (not State components)
      - returns a status message string
    session_id: gr.State holding the current session identifier.

    Returns the Confirm button so the calling section can chain .then() for
    additional outputs (e.g. status message display).
    """
    markdown = gr.Markdown(value=_DRAFT_PLACEHOLDER)
    confirm_btn = gr.Button("Confirmar clasificación", interactive=False)

    draft.change(
        fn=_format_draft,
        inputs=[draft],
        outputs=[markdown, confirm_btn],
    )
    confirm_btn.click(
        fn=confirm_fn,
        inputs=[draft, session_id],
        outputs=[],
    )

    return confirm_btn
```

---

## Plan Completeness

| Category | Status |
|----------|--------|
| Unit tests for `_format_draft` | Not in 8.6 test table — see Risks |
| Live/integration tests | Not applicable (pure UI component) |
| Error handling | `_format_draft` uses `.get()` with safe defaults — no exceptions possible |
| Re-exports | Not applicable — `render_draft_preview` is used directly, not exported from `core` |
| Status updates | Covered in 8.7 |
| Architecture doc | Covered in 8.7 (`clasificacion.md`) |

---

## Out of Scope

- No changes to `render_chat_panel`
- No changes to any section file (that is 8.4)
- No `gr.JSON` fallback
- No section table (per-section `has_data` display removed — section agents handle this in Tasks 9–12)
- No collapsible or tooltip showing all three level descriptions
- `_SECTION_LABELS` constant not needed — removed with section table

---

## Risks and Open Questions

### [OPEN] — `gr.State.change()` Gradio 6.x compatibility
**Problem:** `gr.State.change()` must fire when the state value is updated via a
Gradio event return. Needs confirmation in Gradio 6.x — behavior may differ from
earlier versions.
**Impact:** If `.change()` on a `gr.State` does not fire, the Markdown never updates
and the preview stays as placeholder regardless of conversation progress.
**Suggested action:** Spike with a minimal test before committing to this pattern.
If `.change()` doesn't work, wire the re-render in 8.4 by adding `markdown` and
`confirm_btn` to the send button's output chain and returning them from this function.

### [OPEN] — `_format_draft` not covered in 8.6 test table
**Problem:** `_format_draft` is pure Python and fully testable offline, but no test
for it appears in the 8.6 test plan.
**Impact:** Markdown rendering bugs only surface during manual UI testing.
**Suggested action:** Add to 8.6: `test_format_draft_empty` (no level),
`test_format_draft_level_set` (level present → correct label + description + button enabled).

---

## Deliverable Checklist

### `gradio_app/components.py`
- [ ] `_LEVEL_LABELS`, `_LEVEL_DESCRIPTIONS`, `_DRAFT_PLACEHOLDER` constants added
- [ ] `_format_draft(draft)` returns placeholder + `interactive=False` when draft empty or level is None
- [ ] `_format_draft(draft)` returns Markdown with level label + contextual description when level is set
- [ ] `render_draft_preview()` renders `gr.Markdown` with placeholder as initial value
- [ ] Confirm button starts with `interactive=False`
- [ ] `draft.change()` wired to `_format_draft` → updates markdown + confirm button interactivity
- [ ] `confirm_btn.click()` wired to `confirm_fn` with `inputs=[draft, session_id]`
- [ ] Returns `confirm_btn`
