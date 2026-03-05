import gradio as gr
from gradio_app.session import create_session, get_data_lake
from gradio_app.sections import (
    bienvenida, clasificacion, configuracion,
    alineamiento, estructura, manual_operativo,
)


def build_app() -> gr.Blocks:
    data_lake = get_data_lake()

    with gr.Blocks(title="Zenet MVP 0.1") as demo:
        session_id = gr.State(value="")

        demo.load(fn=lambda: create_session(data_lake), outputs=[session_id])

        with gr.Tabs():
            with gr.Tab("Bienvenida"):
                bienvenida.render(session_id, data_lake)
            with gr.Tab("Clasificación"):
                clasificacion.render(session_id, data_lake)
            with gr.Tab("Configuración"):
                configuracion.render(session_id, data_lake)
            with gr.Tab("Alineamiento"):
                alineamiento.render(session_id, data_lake)
            with gr.Tab("Estructura"):
                estructura.render(session_id, data_lake)
            with gr.Tab("Manual operativo"):
                manual_operativo.render(session_id, data_lake)

    return demo


if __name__ == "__main__":
    build_app().launch()
