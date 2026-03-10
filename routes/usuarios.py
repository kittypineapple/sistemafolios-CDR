from flask import Blueprint, request, redirect, session, render_template
from werkzeug.security import generate_password_hash
from db import get_db_connection
from datetime import datetime

usuarios_bp = Blueprint("usuarios", __name__)

# ==========================
# HELPER AUDITORÍA
# ==========================
def registrar_auditoria(usuario, accion, detalle=None):
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO auditoria (usuario, accion, detalle) VALUES (?, ?, ?)",
            (usuario, accion, detalle)
        )
        conn.commit()

# ==========================
# PANEL PRINCIPAL USUARIOS
# ==========================
@usuarios_bp.route("/admin/usuarios")
def admin_usuarios():
    if session.get("rol") != "admin":
        return redirect("/")
    with get_db_connection() as conn:
        usuarios = conn.execute(
            "SELECT id, username, rol, activo, supervisor FROM usuarios"
        ).fetchall()
    return render_template("admin_usuarios.html", usuarios=usuarios)

# ==========================
# CREAR USUARIO
# ==========================
@usuarios_bp.route("/admin/crear_usuario", methods=["GET", "POST"])
def crear_usuario():
    if session.get("rol") != "admin":
        return redirect("/")
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        rol = request.form.get("rol", "operador")
        try:
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
                    (username, password, rol)
                )
                conn.commit()
            registrar_auditoria(session.get("user"), "CREAR_USUARIO", f"Usuario creado: {username} rol: {rol}")
            return redirect("/admin/usuarios")
        except Exception:
            return render_template("crear_usuario.html", error="El usuario ya existe")
    return render_template("crear_usuario.html")

# ==========================
# ELIMINAR USUARIO
# ==========================
@usuarios_bp.route("/admin/eliminar_usuario/<int:id>", methods=["POST"])
def eliminar_usuario(id):
    if session.get("rol") != "admin":
        return redirect("/")
    with get_db_connection() as conn:
        usuario = conn.execute("SELECT username FROM usuarios WHERE id = ?", (id,)).fetchone()
        conn.execute("DELETE FROM usuarios WHERE id = ?", (id,))
        conn.commit()
    registrar_auditoria(session.get("user"), "ELIMINAR_USUARIO", f"Usuario eliminado: {usuario['username']}")
    return redirect("/admin/usuarios")

# ==========================
# ACTIVAR / DESACTIVAR
# ==========================
@usuarios_bp.route("/admin/toggle_usuario/<int:id>", methods=["POST"])
def toggle_usuario(id):
    if session.get("rol") != "admin":
        return redirect("/")
    with get_db_connection() as conn:
        usuario = conn.execute(
            "SELECT username, activo FROM usuarios WHERE id = ?", (id,)
        ).fetchone()
        nuevo_estado = 0 if usuario["activo"] == 1 else 1
        conn.execute(
            "UPDATE usuarios SET activo = ? WHERE id = ?",
            (nuevo_estado, id)
        )
        conn.commit()
    estado_txt = "activado" if nuevo_estado == 1 else "desactivado"
    registrar_auditoria(session.get("user"), "TOGGLE_USUARIO", f"Usuario {usuario['username']} {estado_txt}")
    return redirect("/admin/usuarios")

# ==========================
# TOGGLE SUPERVISOR
# ==========================
@usuarios_bp.route("/admin/toggle_supervisor/<int:id>", methods=["POST"])
def toggle_supervisor(id):
    if session.get("rol") != "admin":
        return redirect("/")
    with get_db_connection() as conn:
        usuario = conn.execute(
            "SELECT username, supervisor FROM usuarios WHERE id = ?", (id,)
        ).fetchone()
        nuevo_estado = 0 if usuario["supervisor"] == 1 else 1
        conn.execute(
            "UPDATE usuarios SET supervisor = ? WHERE id = ?",
            (nuevo_estado, id)
        )
        conn.commit()
    estado_txt = "marcado supervisor" if nuevo_estado == 1 else "quitado supervisor"
    registrar_auditoria(session.get("user"), "TOGGLE_SUPERVISOR", f"Usuario {usuario['username']} {estado_txt}")
    return redirect("/admin/usuarios")

# ==========================
# VER AUDITORÍA
# ==========================
@usuarios_bp.route("/admin/auditoria")
def auditoria():
    if session.get("rol") != "admin" and session.get("supervisor") != 1:
        return redirect("/")
    with get_db_connection() as conn:
        registros = conn.execute("""
            SELECT * FROM auditoria
            ORDER BY fecha DESC
        """).fetchall()
    return render_template("auditoria.html", registros=registros)
