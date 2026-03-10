import gradio as gr
from typing import Callable


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
    chatbot = gr.Chatbot(label="Asistente Zenet", value=initial_messages)
    textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
    send_btn = gr.Button("Enviar")

    def _handler(message: str, history: list, sid: str) -> tuple[list, str]:
        return chat_fn(message, history, sid)

    send_btn.click(
        fn=_handler,
        inputs=[textbox, chatbot, session_id],
        outputs=[chatbot, textbox],
    )
