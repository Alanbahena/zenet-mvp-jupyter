import gradio as gr

from core.agents.classification_agent import ClassificationAgent

_INITIAL_GREETING = [
    {
        "role": "assistant",
        "content": (
            "Perfecto, sigamos. Ahora necesito entender cómo opera tu restaurante hoy "
            "para asignarte un nivel de estandarización — esto le permitirá a Zenet "
            "adaptar su enfoque en cada sección. "
            "¿Cuántos años lleva operando tu restaurante?"
        ),
    }
]
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES
from gradio_app.components import _format_draft, render_draft_preview
from gradio_app.session import stable_entity_id


def _load_classification_context(data_lake, session_id: str) -> dict:
    entity_id = stable_entity_id(session_id)
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    if not restaurant_data:
        return {}
    context = {"restaurant_name": restaurant_data.get("name")}
    type_id = restaurant_data.get("restaurant_type_id")
    if type_id is not None:
        type_map = {t.id: t.name for t in DEFAULT_RESTAURANT_TYPES}
        context["restaurant_type"] = type_map.get(type_id)
    return context


def _make_chat_fn(provider, data_lake):
    def chat_fn(message, history, session_id):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, "", {}
        if not (message or "").strip():
            return history, "", {}
        agent = create_agent(ClassificationAgent, provider=provider, name="classification_agent")
        agent.load_state(data_lake, session_id=f"classification_agent_{session_id}")
        context = _load_classification_context(data_lake, session_id)
        try:
            result = agent.run(input_data={"user_message": message}, context=context)
            reply = result["reply"]
        except Exception:
            reply = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
        agent.save_state(data_lake, session_id=f"classification_agent_{session_id}")
        history = list(history)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        level = agent.retrieve("standardization_level")
        description = agent.retrieve("restaurant_description")
        description_raw = agent.retrieve("restaurant_description_raw")
        draft_dict = {"standardization_level": level} if level is not None else {}
        if description is not None:
            draft_dict["restaurant_description"] = description
        if description_raw is not None:
            draft_dict["restaurant_description_raw"] = description_raw
        return history, "", draft_dict
    return chat_fn


def _make_confirm_fn(data_lake):
    def confirm_fn(draft_dict, session_id):
        if not session_id:
            return "Sesión no iniciada. Recarga la página."
        level = (draft_dict or {}).get("standardization_level")
        if level is None:
            return "La clasificación no está completa. Continúa la conversación con el asistente."
        entity_id = stable_entity_id(session_id)
        try:
            classification_dict = {"standardization_level": level}
            description = (draft_dict or {}).get("restaurant_description")
            description_raw = (draft_dict or {}).get("restaurant_description_raw")
            if description is not None:
                classification_dict["restaurant_description"] = description
            if description_raw is not None:
                classification_dict["restaurant_description_raw"] = description_raw
            data_lake.save_entity("classification", entity_id, classification_dict)
        except Exception:
            return "Error al guardar la clasificación. Por favor, intenta de nuevo."
        from gradio_app.components import _LEVEL_LABELS
        label = _LEVEL_LABELS.get(level, f"Nivel {level}")
        return (
            f"Listo. Tu restaurante queda registrado en **{label}**. "
            f"Ya puedes continuar con el paso 3 — **Configuración inicial** — "
            f"en la barra de navegación."
        )
    return confirm_fn


def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()
    draft_state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de clasificación")
            chatbot = gr.Chatbot(label="Asistente Zenet", value=_INITIAL_GREETING, height="70vh")
            textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False, lines=3, max_lines=3)
            send_btn = gr.Button("Enviar")

        with gr.Column(scale=1):
            gr.Markdown("## Clasificación propuesta")
            draft_markdown, confirm_btn = render_draft_preview(
                draft=draft_state,
                confirm_fn=_make_confirm_fn(data_lake),
                session_id=session_id,
            )

    chat_fn = _make_chat_fn(provider, data_lake)

    def _chat_and_format(message, history, session_id):
        history, text, draft_dict = chat_fn(message, history, session_id)
        md, btn = _format_draft(draft_dict)
        return history, text, draft_dict, md, btn

    send_btn.click(
        fn=_chat_and_format,
        inputs=[textbox, chatbot, session_id],
        outputs=[chatbot, textbox, draft_state, draft_markdown, confirm_btn],
    )
