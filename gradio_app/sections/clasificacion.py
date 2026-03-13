import gradio as gr

from core.agents.classification_agent import ClassificationAgent
from core.agents.utils import create_agent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES
from gradio_app.components import render_draft_preview


def _load_classification_context(data_lake, session_id: str) -> dict:
    entity_id = abs(hash(session_id)) % (2**31 - 1)
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
        draft_dict = {"standardization_level": level} if level is not None else {}
        return history, "", draft_dict
    return chat_fn


def _make_confirm_fn(data_lake):
    def confirm_fn(draft_dict, session_id):
        if not session_id:
            return "Sesión no iniciada. Recarga la página."
        level = (draft_dict or {}).get("standardization_level")
        if level is None:
            return "La clasificación no está completa. Continúa la conversación con el asistente."
        entity_id = abs(hash(session_id)) % (2**31 - 1)
        try:
            data_lake.save_entity("classification", entity_id, {"standardization_level": level})
        except Exception:
            return "Error al guardar la clasificación. Por favor, intenta de nuevo."
        return f"Clasificación guardada: Nivel {level}."
    return confirm_fn


def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()
    draft_state = gr.State({})

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Asistente de clasificación")
            chatbot = gr.Chatbot(label="Asistente Zenet", height="70vh")
            textbox = gr.Textbox(placeholder="Escribe tu mensaje...", show_label=False)
            send_btn = gr.Button("Enviar")

        with gr.Column(scale=1):
            gr.Markdown("## Clasificación propuesta")
            render_draft_preview(
                draft=draft_state,
                confirm_fn=_make_confirm_fn(data_lake),
                session_id=session_id,
            )

    chat_fn = _make_chat_fn(provider, data_lake)
    send_btn.click(
        fn=chat_fn,
        inputs=[textbox, chatbot, session_id],
        outputs=[chatbot, textbox, draft_state],
    )
