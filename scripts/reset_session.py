import os

db_path = os.path.join(os.path.dirname(__file__), "..", "data", "zenet.db")
if os.path.exists(db_path):
    os.remove(db_path)
    print("Sesión borrada. Reinicia la aplicación para empezar de nuevo.")
else:
    print("No hay sesión activa.")
