from werkzeug.security import generate_password_hash
from db import get_db_connection

def crear_admin():
    username = input("Usuario admin: ")
    password = input("Contraseña: ")
    
    hashed = generate_password_hash(password)
    
    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO usuarios (username, password, rol, activo) VALUES (?, ?, ?, ?)",
                (username, hashed, "admin", 1)
            )
            conn.commit()
        print(f"✔ Admin '{username}' creado exitosamente")
    except Exception as e:
        print(f"Error: {e} — ¿El usuario ya existe?")

if __name__ == "__main__":
    crear_admin()
