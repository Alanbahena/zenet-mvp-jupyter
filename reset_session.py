import os

db_path = "data/zenet.db"
if os.path.exists(db_path):
    os.remove(db_path)
    print("Sesión borrada. Reinicia la aplicación para empezar de nuevo.")
else:
    print("No hay sesión activa.")
