from werkzeug.security import generate_password_hash
from db import get_db_connection

username = input("Usuario a modificar: ")
password = input("Nueva contraseña: ")

hashed = generate_password_hash(password)

with get_db_connection() as conn:
    conn.execute(
        "UPDATE usuarios SET password = ? WHERE username = ?",
        (hashed, username)
    )
    conn.commit()
print(f"✔ Contraseña de '{username}' actualizada")
