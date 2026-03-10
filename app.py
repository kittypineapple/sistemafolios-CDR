from flask import Flask, request, session, redirect, url_for, render_template
from werkzeug.security import check_password_hash
from db import init_db, get_db_connection
from routes.documentos import docs_bp
from routes.usuarios import usuarios_bp
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key_local")

# Registrar blueprints
app.register_blueprint(docs_bp)
app.register_blueprint(usuarios_bp)

with app.app_context():
    init_db()

# -------------------------------------------------
# PROTECCIÓN GLOBAL (ANTES DE CADA REQUEST)
# -------------------------------------------------
@app.before_request
def proteger_rutas():
    rutas_publicas = ["login", "static"]
    if request.endpoint not in rutas_publicas and "user" not in session:
        return redirect(url_for("login"))

# -------------------------------------------------
# HOME
# -------------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with get_db_connection() as conn:
            user = conn.execute(
                "SELECT * FROM usuarios WHERE username = ?",
                (username,)
            ).fetchone()
        if user and check_password_hash(user["password"], password) and user["activo"] == 1:
            session["user"] = user["username"]
            session["rol"] = user["rol"]
            session["supervisor"] = user["supervisor"]
            with get_db_connection() as conn:
                conn.execute(
                    "INSERT INTO auditoria (usuario, accion, detalle) VALUES (?, ?, ?)",
                    (user["username"], "LOGIN", "Inicio de sesión exitoso")
                )
                conn.commit()
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")

# -------------------------------------------------
# LOGOUT
# -------------------------------------------------
@app.route("/logout")
def logout():
    usuario = session.get("user")
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO auditoria (usuario, accion, detalle) VALUES (?, ?, ?)",
            (usuario, "LOGOUT", "Cierre de sesión")
        )
        conn.commit()
    session.clear()
    return redirect(url_for("login"))
# -------------------------------------------------
# ARRANQUE
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)