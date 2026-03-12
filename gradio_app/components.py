import gradio as gr
from typing import Callable

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


def _format_draft(draft: dict) -> tuple[str, dict]:
    """
    Convert a classification draft dict to a Markdown string and a button update.

    Returns (markdown_str, gr.update(interactive=bool)).
    Shows the diagnosed level label and a one-line contextual description.
    Returns placeholder text and a disabled button when draft is empty or level is not yet set.
    """
    level = (draft or {}).get("standardization_level")
    if level is None:
        return _DRAFT_PLACEHOLDER, gr.update(interactive=False)
    label = _LEVEL_LABELS.get(level, f"Nivel {level}")
    description = _LEVEL_DESCRIPTIONS.get(level, "")
    markdown = f"**{label}**\n{description}"
    return markdown, gr.update(interactive=True)


def render_chat_panel(
    chat_fn: Callable,
    session_id: gr.State,
    data_lake_ref: object,
    initial_messages: list[dict[str, str]] | None = None,
) -> None:
    """
    Render the right-column chat panel inside an active gr.Column context.

    Renders: gr.Chatbot + gr.Textbox (user input) + Send gr.Button.
    Send button click calls chat_fn and updates the chatbot history.

    chat_fn signature: (message: str, history: list, session_id: str) -> tuple[list, str]
      - history uses Gradio 6.x messages format: list[{"role": str, "content": str}]
      - returns: (updated_history, "") where updated_history appends user + assistant turns
      - example:
          history.append({"role": "user",      "content": message})
          history.append({"role": "assistant",  "content": response})
          return history, ""

    data_lake_ref is NOT a Gradio component and cannot be a Gradio event handler input.
    data_lake_ref is accepted as a parameter but is NOT passed to chat_fn by this component.
    Gradio wires only [textbox, chatbot, session_id] as component inputs.
    Tasks 7-12 define chat_fn as receiving (message, history, session_id) — data_lake is
    already in scope inside chat_fn via the section's own closure over data_lake.

    initial_messages: Optional list of pre-loaded chat messages in Gradio messages format:
      [{"role": "assistant", "content": "..."}]. When provided, the chatbot renders these
      messages on load (used for Bienvenida's static auto-greeting). Default None — chatbot
      starts empty for all other sections.

    Layout note: sections that need a bottom data/table row may add a gr.Row after the
    two-column block in their render() function. See Decision 6 in the Task 6 plan.
    """
    chatbot = gr.Chatbot(label="Asistente Zenet", value=initial_messages, height="70vh")
    textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
    send_btn = gr.Button("Enviar")

    def _handler(message: str, history: list, sid: str) -> tuple[list, str]:
        return chat_fn(message, history, sid)

    send_btn.click(
        fn=_handler,
        inputs=[textbox, chatbot, session_id],
        outputs=[chatbot, textbox],
    )


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
