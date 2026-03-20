import gradio as gr
from typing import Callable

_LEVEL_LABELS = {
    1: "Nivel 1 — Operación en la cabeza",
    2: "Nivel 2 — Parcialmente documentado",
    3: "Nivel 3 — Operación estructurada",
}
_LEVEL_DESCRIPTIONS = {
    1: (
        "Tu operación vive en la cabeza de tu equipo. Las recetas se hacen de memoria, "
        "el inventario se maneja a ojo, y si un empleado clave falta, algo se desordena. "
        "No hay nada malo en eso — muchos restaurantes exitosos operan así. "
        "Pero Zenet va a ayudarte a convertir ese conocimiento en un sistema."
    ),
    2: (
        "Tienes algo escrito, pero está disperso. Quizás un Excel con recetas, "
        "una lista de proveedores en WhatsApp, o fotos de los platillos. "
        "Funciona, pero depende de que la persona correcta sepa dónde está cada cosa. "
        "Zenet va a tomar todo eso y darle un lugar."
    ),
    3: (
        "Tu operación está documentada y organizada. Tienes recetas con cantidades, "
        "inventario controlado, y procesos que tu equipo puede seguir sin preguntarte. "
        "Zenet va a conectar todo eso para que puedas ver tu negocio como un sistema completo."
    ),
}
_LEVEL_NEXT_STEPS = {
    1: (
        "No te preocupes si no tienes nada escrito — para eso estamos aquí. "
        "Vamos a construir todo juntos desde cero, paso a paso. "
        "Tú solo respondes y Zenet va armando tu operación contigo."
    ),
    2: (
        "Lo que ya tienes es un buen punto de partida. "
        "Vamos a tomar lo que existe — aunque esté incompleto — y completar lo que falte. "
        "Piénsalo como ordenar una cocina: usamos lo que hay y conseguimos lo que falta."
    ),
    3: (
        "Llevas ventaja — ya tienes mucho trabajo hecho. "
        "Vamos a tomar toda esa información y organizarla dentro de Zenet para que funcione como un sistema. "
        "El trabajo ya está, solo hay que darle estructura."
    ),
}
_LEVEL_SHORT = {
    1: "Todo vive en la memoria del equipo, sin nada escrito.",
    2: "Algo escrito y disperso: Excel, notas, fotos — pero sin un sistema.",
    3: "Recetas, inventario y procesos documentados y organizados.",
}
_SPECTRUM_PENDING = """\
Responde las preguntas del asistente para que Zenet pueda determinar tu nivel.

---

**Nivel 1 — Operación en la cabeza**
Todo vive en la memoria del equipo, sin nada escrito.

**Nivel 2 — Parcialmente documentado**
Algo escrito y disperso: Excel, notas, fotos — pero sin un sistema.

**Nivel 3 — Operación estructurada**
Recetas, inventario y procesos documentados y organizados.\
"""


def _format_draft(draft: dict) -> tuple[str, dict]:
    """
    Convert a classification draft dict to a Markdown string and a button update.

    Returns (markdown_str, gr.update(interactive=bool)).

    No level set: shows the full spectrum as a reference so the operator knows
    what they are working toward during the conversation.

    Level set: shows the diagnosed level prominently, its implication for next
    sections, and the full spectrum with the current level marked.
    """
    level = (draft or {}).get("standardization_level")
    if level is None:
        return _SPECTRUM_PENDING, gr.update(interactive=False)

    label = _LEVEL_LABELS.get(level, f"Nivel {level}")
    description = _LEVEL_DESCRIPTIONS.get(level, "")
    next_steps = _LEVEL_NEXT_STEPS.get(level, "")

    spectrum_lines = []
    for lvl in (1, 2, 3):
        row_label = _LEVEL_LABELS.get(lvl, f"Nivel {lvl}")
        row_short = _LEVEL_SHORT.get(lvl, "")
        if lvl == level:
            spectrum_lines.append(f"> **{row_label}** — tu nivel\n> {row_short}")
        else:
            spectrum_lines.append(f"{row_label}\n{row_short}")
    spectrum = "\n\n".join(spectrum_lines)

    markdown = (
        f"**Tu restaurante está en {label}**\n"
        f"{description}\n\n"
        f"**Próximas secciones:** {next_steps}\n\n"
        f"---\n\n"
        f"{spectrum}"
    )
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
    textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False, lines=3, max_lines=3)
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
) -> tuple[gr.Markdown, gr.Button]:
    """
    Render the right-column draft preview panel inside an active gr.Column context.

    Renders: gr.Markdown (live classification draft) + Confirm gr.Button.
    The Confirm button is disabled until standardization_level is set in the draft.

    draft: gr.State holding the current classification draft dict
           (keys: standardization_level).
    confirm_fn signature: (draft_dict: dict, session_id: str) -> str
      - receives the draft dict and session_id values (not State components)
      - returns a status message string
    session_id: gr.State holding the current session identifier.

    Returns (markdown, confirm_btn) so the calling section can wire them as
    outputs of a .then() chain on the send button click event. gr.State.change()
    does not fire when a State is updated via a click handler return value, so
    the caller must chain .then(fn=_format_draft, inputs=[draft], outputs=[markdown, confirm_btn])
    directly off the send button.
    """
    markdown = gr.Markdown(value=_SPECTRUM_PENDING)
    confirm_btn = gr.Button("Confirmar clasificación", interactive=False)
    status = gr.Markdown("")

    confirm_btn.click(
        fn=confirm_fn,
        inputs=[draft, session_id],
        outputs=[status],
    )

    return markdown, confirm_btn
