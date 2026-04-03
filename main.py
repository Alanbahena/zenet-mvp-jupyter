from gradio_app.app import build_app

if __name__ == "__main__":
    build_app().launch(server_name="0.0.0.0", server_port=7860)
