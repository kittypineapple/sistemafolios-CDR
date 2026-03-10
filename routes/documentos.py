from flask import Blueprint, render_template, request, redirect
from flask import session
from datetime import datetime
from functools import wraps
from db import get_db_connection, get_fecha_mexico

docs_bp = Blueprint("documentos", __name__)

# -------------------------------------------------
# HELPER AUDITORÍA
# -------------------------------------------------
def registrar_auditoria(usuario, accion, detalle=None):
    with get_db_connection() as conn:
        conn.execute(
            "INSERT INTO auditoria (usuario, accion, detalle, fecha) VALUES (?, ?, ?, ?)",
            (usuario, accion, detalle, get_fecha_mexico())
        )
        conn.commit()

# -------------------------------------------------
# CONTROL DE ROLES
# -------------------------------------------------
def rol_requerido(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("rol") not in roles:
                return redirect("/")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# -------------------------------------------------
# GENERADOR DE FOLIOS
# -------------------------------------------------
@docs_bp.route("/generar")
@rol_requerido("admin", "operador")
def generar():
    return render_template("generar_folio.html")

# -------------------------------------------------
# GUARDAR DOCUMENTO + GENERAR FOLIO MULTIFORMATO
# -------------------------------------------------
@docs_bp.route("/guardar", methods=["POST"])
@rol_requerido("admin", "operador")
def guardar():
    try:
        with get_db_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.cursor()

            tipo = request.form["tipo_doc"].strip().upper()

            if tipo == "IES":
                dependencia = "AREAS OPERATIVAS"
                oficio_responder = ""
                tipo_solicitud = ""
                quien_solicita = ""
                quien_aprueba = ""
            else:
                dependencia = request.form["dependencia"]
                oficio_responder = request.form.get("oficio_responder", "")
                tipo_solicitud = request.form.get("tipo_solicitud", "")
                quien_solicita = request.form.get("quien_solicita", "")
                quien_aprueba = request.form.get("quien_aprueba", "")

            # fecha del formulario para el folio
            fecha_form = request.form["fecha"]
            fecha_dt = datetime.strptime(fecha_form, "%Y-%m-%d")

            año = fecha_dt.year
            mes = f"{fecha_dt.month:02d}"
            anio_corto = str(año)[2:]
            anio_mes = f"{anio_corto}{mes}"
            dia_del_anio = fecha_dt.timetuple().tm_yday

            # ── CALCULAR FOLIO BASE Y VERIFICAR SI YA EXISTE ──────────
            if tipo == "IES":
                numero_dia = f"{dia_del_anio:03d}"
                folio_base = f"TM-IE-{año}-{numero_dia}"

                existe = cursor.execute("""
                    SELECT folio FROM documentos
                    WHERE folio LIKE ?
                    ORDER BY id DESC LIMIT 1
                """, (f"{folio_base}%",)).fetchone()

                if existe:
                    conn.rollback()
                    return render_template("generar_folio.html",
                        error=f"El folio {existe['folio']} ya existe para esta fecha. Usa el módulo de Actualizar Versión.")

                folio_final = f"{folio_base}-V1"

            elif tipo == "PROYECCIONES":
                cursor.execute("""
                    SELECT folio FROM documentos
                    WHERE tipo_doc = ? AND folio LIKE '%-V1.0'
                """, (tipo,))
                todos = cursor.fetchall()
                if todos:
                    numeros = [int(f["folio"].split("-")[-2]) for f in todos]
                    nuevo_indice = max(numeros) + 1
                else:
                    nuevo_indice = 1
                folio_base  = f"TMM-{anio_mes}-CGSCF-{dependencia}-{nuevo_indice:03d}"
                folio_final = f"{folio_base}-V1.0"

                existe = cursor.execute("""
                    SELECT folio FROM documentos
                    WHERE folio LIKE ?
                """, (f"{folio_base}%",)).fetchone()

                if existe:
                    conn.rollback()
                    return render_template("generar_folio.html",
                        error=f"El folio {existe['folio']} ya existe. Usa el módulo de Actualizar Versión.")

            elif tipo == "ATTRAPI":
                cursor.execute("""
                    SELECT folio FROM documentos
                    WHERE tipo_doc = ? AND dependencia = ?
                    ORDER BY id DESC LIMIT 1
                """, (tipo, dependencia))
                ultimo = cursor.fetchone()
                nuevo_indice = int(ultimo["folio"].split("-")[-2]) + 1 if ultimo else 1
                folio_base  = f"TMM-{anio_mes}-CGSCF-ATTRAPI-{nuevo_indice:02d}"
                folio_final = f"{folio_base}-V1.0"

                existe = cursor.execute("""
                    SELECT folio FROM documentos
                    WHERE folio LIKE ?
                """, (f"{folio_base}%",)).fetchone()

                if existe:
                    conn.rollback()
                    return render_template("generar_folio.html",
                        error=f"El folio {existe['folio']} ya existe. Usa el módulo de Actualizar Versión.")
            else:
                return "Tipo de documento inválido"
            # ──────────────────────────────────────────────────────────

            usuario = conn.execute(
                "SELECT id FROM usuarios WHERE username = ?",
                (session.get("user"),)
            ).fetchone()
            usuario_id = usuario["id"] if usuario else None

            cursor.execute("""
                INSERT INTO documentos (
                    folio, tipo_doc, fecha, personal_elabora,
                    persona_firma, dependencia, persona_dirigida,
                    oficio_responder, asunto, tipo_solicitud,
                    quien_solicita, quien_aprueba, usuario_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                folio_final, tipo,
                request.form["fecha"], request.form["personal_elabora"],
                request.form["persona_firma"], dependencia,
                request.form["persona_dirigida"], oficio_responder,
                request.form["asunto"], tipo_solicitud,
                quien_solicita, quien_aprueba, usuario_id
            ))
            conn.commit()

        registrar_auditoria(session.get("user"), "GENERAR_FOLIO", f"Folio generado: {folio_final}")
        return render_template("folio_generado.html", folio=folio_final, tipo_doc=tipo, dependencia=dependencia)

    except Exception as e:
        print(f"Error al guardar folio: {e}")
        return render_template("folio_generado.html", folio="ERROR", tipo_doc="N/A", dependencia="")

# -------------------------------------------------
# CONSULTA DE FOLIOS
# -------------------------------------------------
@docs_bp.route("/consulta")
@rol_requerido("admin", "operador", "consulta")
def consulta():
    return render_template("consulta_folio.html")

@docs_bp.route("/buscar_palabra", methods=["POST"])
@rol_requerido("admin", "operador", "consulta")
def buscar_palabra():
    palabra = request.form.get("palabra")
    with get_db_connection() as conn:
        resultados = conn.execute("""
            SELECT * FROM documentos WHERE asunto LIKE ?
            ORDER BY fecha_registro DESC
        """, (f"%{palabra}%",)).fetchall()
    return render_template("resultado_lista.html", resultados=resultados)

@docs_bp.route("/buscar_tipo", methods=["POST"])
@rol_requerido("admin", "operador", "consulta")
def buscar_tipo():
    tipo = request.form.get("tipo_doc")
    with get_db_connection() as conn:
        resultados = conn.execute("""
            SELECT * FROM documentos WHERE tipo_doc = ?
            ORDER BY fecha_registro DESC
        """, (tipo,)).fetchall()
    return render_template("resultado_lista.html", resultados=resultados)

@docs_bp.route("/buscar_folio", methods=["POST"])
@rol_requerido("admin", "operador", "consulta")
def buscar_folio():
    folio = request.form.get("folio")
    with get_db_connection() as conn:
        resultado = conn.execute("SELECT * FROM documentos WHERE folio = ?", (folio,)).fetchone()
        versiones = []
        if resultado:
            base = resultado['folio'].split("-V")[0]
            versiones = conn.execute("""
                SELECT folio, fecha, personal_elabora FROM documentos
                WHERE folio LIKE ? ORDER BY folio ASC
            """, (base + "-V%",)).fetchall()
    return render_template("resultado_folio.html", resultado=resultado, versiones=versiones)

@docs_bp.route("/buscar_folio_get/<folio>")
@rol_requerido("admin", "operador", "consulta")
def buscar_folio_get(folio):
    with get_db_connection() as conn:
        resultado = conn.execute("SELECT * FROM documentos WHERE folio = ?", (folio,)).fetchone()
        versiones = []
        if resultado:
            base = resultado['folio'].split("-V")[0]
            versiones = conn.execute("""
                SELECT folio, fecha, personal_elabora FROM documentos
                WHERE folio LIKE ? ORDER BY folio ASC
            """, (base + "-V%",)).fetchall()
    return render_template("resultado_folio.html", resultado=resultado, versiones=versiones)

# -------------------------------------------------
# ACTUALIZAR VERSIÓN
# -------------------------------------------------
@docs_bp.route("/version")
@rol_requerido("admin", "operador")
def version():
    return render_template("nueva_version.html")

@docs_bp.route("/form_nueva_version", methods=["POST"])
@rol_requerido("admin", "operador")
def form_nueva_version():
    folio = request.form.get("folio")
    with get_db_connection() as conn:
        documento = conn.execute(
            "SELECT * FROM documentos WHERE folio = ?", (folio,)
        ).fetchone()
    if not documento:
        return render_template("nueva_version.html", error="Folio no encontrado")
    return render_template("nueva_version.html", documento=documento)

@docs_bp.route("/guardar_version", methods=["POST"])
@rol_requerido("admin", "operador")
def guardar_version():
    folio_anterior   = request.form.get("folio_anterior")
    fecha            = request.form.get("fecha")
    personal_elabora = request.form.get("personal_elabora")
    persona_firma    = request.form.get("persona_firma")
    dependencia      = request.form.get("dependencia")
    persona_dirigida = request.form.get("persona_dirigida")
    oficio_responder = request.form.get("oficio_responder", "")
    tipo_solicitud   = request.form.get("tipo_solicitud", "")
    quien_solicita   = request.form.get("quien_solicita", "")
    quien_aprueba    = request.form.get("quien_aprueba", "")
    asunto           = request.form.get("asunto")

    base = folio_anterior.split("-V")[0]

    try:
        with get_db_connection() as conn:

            doc_original = conn.execute(
                "SELECT tipo_doc FROM documentos WHERE folio = ?", (folio_anterior,)
            ).fetchone()
            tipo_doc = doc_original["tipo_doc"] if doc_original else ""

            if tipo_doc == "IES":
                dependencia      = "ÁREAS OPERATIVAS"
                tipo_solicitud   = ""
                oficio_responder = ""
                quien_solicita   = ""
                quien_aprueba    = ""

            versiones = conn.execute(
                "SELECT folio FROM documentos WHERE folio LIKE ?", (base + "-V%",)
            ).fetchall()
            max_version = 1.0
            for v in versiones:
                try:
                    n = float(v["folio"].split("-V")[1])
                    if n > max_version:
                        max_version = n
                except:
                    pass
            nueva_version = round(max_version + 0.1, 1)
            nuevo_folio   = f"{base}-V{nueva_version}"

            usuario = conn.execute(
                "SELECT id FROM usuarios WHERE username = ?", (session.get("user"),)
            ).fetchone()
            usuario_id = usuario["id"] if usuario else None

            conn.execute("""
                INSERT INTO documentos (
                    folio, fecha, personal_elabora, persona_firma,
                    dependencia, persona_dirigida, oficio_responder,
                    asunto, tipo_solicitud, quien_solicita, quien_aprueba,
                    tipo_doc, usuario_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nuevo_folio, fecha, personal_elabora, persona_firma,
                dependencia, persona_dirigida, oficio_responder,
                asunto, tipo_solicitud, quien_solicita, quien_aprueba,
                tipo_doc, usuario_id
            ))

            conn.execute("""
                INSERT INTO historial_versiones (folio_anterior, folio_nuevo, usuario, motivo, fecha)
                VALUES (?, ?, ?, ?, ?)
            """, (folio_anterior, nuevo_folio, session.get("user"), asunto, get_fecha_mexico()))

            conn.commit()

            versiones = conn.execute(
                "SELECT * FROM documentos WHERE folio LIKE ? ORDER BY folio ASC",
                (base + "-V%",)
            ).fetchall()

        registrar_auditoria(
            session.get("user"), "ACTUALIZAR_VERSION",
            f"Versión actualizada: {folio_anterior} → {nuevo_folio}"
        )
        return render_template(
            "version_creada.html",
            nuevo_folio=nuevo_folio,
            documento={
                "fecha": fecha, "personal_elabora": personal_elabora,
                "persona_firma": persona_firma, "dependencia": dependencia,
                "persona_dirigida": persona_dirigida, "oficio_responder": oficio_responder,
                "asunto": asunto, "tipo_solicitud": tipo_solicitud,
                "quien_solicita": quien_solicita, "quien_aprueba": quien_aprueba,
                "tipo_doc": tipo_doc,
            },
            versiones=versiones
        )

    except Exception as e:
        print(f"Error al guardar versión: {e}")
        return render_template("version_creada.html", error=str(e))

# -------------------------------------------------
# ADJUNTAR DOCUMENTOS
# -------------------------------------------------
@docs_bp.route("/adjuntar")
@rol_requerido("admin", "operador")
def adjuntar():
    return render_template("adjuntar_documentos.html")

@docs_bp.route("/form_adjuntar_documentos", methods=["POST"])
@rol_requerido("admin", "operador")
def form_adjuntar():
    folio = request.form.get("folio")
    with get_db_connection() as conn:
        documento = conn.execute("SELECT * FROM documentos WHERE folio = ?", (folio,)).fetchone()
    if not documento:
        return render_template("adjuntar_documentos.html", error="Folio no encontrado")
    return render_template("adjuntar_documentos.html", documento=documento)

@docs_bp.route("/cargar_link/<folio>/<tipo_adjunto>")
@rol_requerido("admin", "operador")
def cargar_link(folio, tipo_adjunto):
    with get_db_connection() as conn:
        documento = conn.execute("SELECT * FROM documentos WHERE folio = ?", (folio,)).fetchone()
    if not documento:
        return render_template("adjuntar_documentos.html", error="Folio no encontrado")
    return render_template("cargar_documentos.html", documento=documento, tipo_adjunto=tipo_adjunto)

@docs_bp.route("/guardar_link", methods=["POST"])
@rol_requerido("admin", "operador")
def guardar_link():
    folio        = request.form.get("folio")
    tipo_adjunto = request.form.get("tipo_adjunto")
    link         = request.form.get("link")

    with get_db_connection() as conn:
        if tipo_adjunto == "acuse":
            conn.execute("UPDATE documentos SET acuse = ? WHERE folio = ?", (link, folio))
        elif tipo_adjunto == "presentacion":
            conn.execute("UPDATE documentos SET presentacion = ? WHERE folio = ?", (link, folio))
        conn.commit()
        documento = conn.execute("SELECT * FROM documentos WHERE folio = ?", (folio,)).fetchone()

    registrar_auditoria(session.get("user"), "CARGAR_LINK", f"Link {tipo_adjunto} cargado en folio: {folio}")

    return render_template(
        "cargar_documentos.html",
        documento=documento,
        tipo_adjunto=tipo_adjunto,
        link=link,
        responsable=request.form.get("responsable"),
        fecha=datetime.now().strftime("%d/%m/%Y %H:%M"),
        guardado=True
    )