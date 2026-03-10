import gradio as gr

from core.agents.utils import create_agent
from core.agents.welcome_agent import WelcomeAgent
from core.ai.providers import ClaudeProvider
from core.domain.data_model import DEFAULT_RESTAURANT_TYPES, Restaurant, User
from core.domain.serialization import restaurant_to_dict, user_to_dict
from gradio_app.components import render_chat_panel


_RESTAURANT_TYPE_OPTIONS = [t.name for t in DEFAULT_RESTAURANT_TYPES]
_RESTAURANT_TYPE_NAME_TO_ID = {t.name: t.id for t in DEFAULT_RESTAURANT_TYPES}
_INITIAL_GREETING = [
    {
        "role": "assistant",
        "content": (
            "Hola, soy Zeni, tu asistente de bienvenida en Zenet. "
            "Estoy aquí para acompañarte durante este proceso y resolver "
            "cualquier duda que tengas sobre Zenet o el registro. "
            "¿Por dónde quieres empezar?"
        ),
    }
]


def _load_form_context(data_lake, session_id: str) -> dict:
    entity_id = abs(hash(session_id)) % (2**31 - 1)
    restaurant_data = data_lake.load_entity("restaurant", entity_id)
    user_data = data_lake.load_entity("user", entity_id)
    if restaurant_data and user_data:
        return {
            "operator_name": user_data["name"],
            "restaurant_name": restaurant_data["name"],
        }
    return {}


def _make_save_fn(data_lake):
    def save_fn(user_name, restaurant_name, restaurant_type_label, session_id):
        if not session_id:
            return "Sesión no iniciada. Recarga la página e intenta de nuevo.", gr.update()
        if not (user_name or "").strip():
            return "El nombre del operador es obligatorio.", gr.update()
        if not (restaurant_name or "").strip():
            return "El nombre del restaurante es obligatorio.", gr.update()
        entity_id = abs(hash(session_id)) % (2**31 - 1)
        restaurant_type_id = _RESTAURANT_TYPE_NAME_TO_ID.get(restaurant_type_label)
        restaurant = Restaurant(
            id=entity_id,
            name=restaurant_name.strip(),
            restaurant_type_id=restaurant_type_id,
        )
        user = User(
            id=entity_id,
            name=user_name.strip(),
            email=f"{session_id}@zenet.local",
            role="admin",
        )
        data_lake.save_entity("restaurant", entity_id, restaurant_to_dict(restaurant))
        data_lake.save_entity("user", entity_id, user_to_dict(user))
        return (
            f"Registro guardado. Bienvenido, {user.name}.",
            gr.update(value="Registro guardado", interactive=False),
        )
    return save_fn


def _make_chat_fn(provider, data_lake):
    def chat_fn(message, history, session_id):
        if not session_id:
            history = list(history)
            history.append({"role": "assistant", "content": "Sesión no iniciada. Recarga la página."})
            return history, ""
        if not (message or "").strip():
            return history, ""
        agent = create_agent(WelcomeAgent, provider=provider, name="welcome_agent")
        agent.load_state(data_lake, session_id=f"welcome_agent_{session_id}")
        context = _load_form_context(data_lake, session_id)
        try:
            result = agent.run(input_data={"user_message": message}, context=context)
            reply = result["reply"]
        except Exception:
            reply = "Hubo un problema al conectar con el asistente. Por favor, intenta de nuevo."
        agent.save_state(data_lake, session_id=f"welcome_agent_{session_id}")
        history = list(history)
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""
    return chat_fn


def render(session_id: gr.State, data_lake) -> None:
    provider = ClaudeProvider()

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## Registro inicial")
            name_input = gr.Textbox(label="Tu nombre")
            restaurant_input = gr.Textbox(label="Nombre del restaurante")
            type_dropdown = gr.Dropdown(
                choices=_RESTAURANT_TYPE_OPTIONS,
                label="Tipo de restaurante",
                value=None,
            )
            save_btn = gr.Button("Guardar registro", variant="primary")
            save_status = gr.Markdown("")

        with gr.Column(scale=1):
            gr.Markdown("## Asistente de bienvenida")
            render_chat_panel(
                chat_fn=_make_chat_fn(provider, data_lake),
                session_id=session_id,
                data_lake_ref=data_lake,
                initial_messages=_INITIAL_GREETING,
            )

    save_btn.click(
        fn=_make_save_fn(data_lake),
        inputs=[name_input, restaurant_input, type_dropdown, session_id],
        outputs=[save_status, save_btn],
    )

    for field in [name_input, restaurant_input, type_dropdown]:
        field.change(
            fn=lambda: gr.update(value="Guardar registro", interactive=True),
            inputs=[],
            outputs=[save_btn],
        )
