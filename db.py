import sqlite3
import os
from datetime import datetime, timezone, timedelta

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "folios.db")
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)


def get_fecha_mexico():
    tz_mexico = timezone(timedelta(hours=-6))
    return datetime.now(tz_mexico).strftime("%Y-%m-%d %H:%M:%S")

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE,
            tipo_doc TEXT,
            fecha TEXT,
            usuario_id INTEGER,
            personal_elabora TEXT,
            persona_firma TEXT,
            dependencia TEXT,
            persona_dirigida TEXT,
            oficio_responder TEXT,
            tipo_solicitud TEXT,
            quien_solicita TEXT,
            quien_aprueba TEXT,
            asunto TEXT,
            acuse TEXT,
            presentacion TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_versiones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio_anterior TEXT NOT NULL,
            folio_nuevo TEXT NOT NULL,
            usuario TEXT NOT NULL,
            motivo TEXT NOT NULL,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'operador',
            activo INTEGER DEFAULT 1,
            supervisor INTEGER DEFAULT 0
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            accion TEXT NOT NULL,
            detalle TEXT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # Migraciones para BD existente
        for columna in ["acuse", "presentacion"]:
            try:
                cursor.execute(f"ALTER TABLE documentos ADD COLUMN {columna} TEXT")
            except sqlite3.OperationalError:
                pass

        try:
            cursor.execute("ALTER TABLE usuarios ADD COLUMN supervisor INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        for columna in ["tipo_solicitud", "quien_solicita", "quien_aprueba"]:
            try:
                cursor.execute(f"ALTER TABLE documentos ADD COLUMN {columna} TEXT")
            except sqlite3.OperationalError:
                pass

        conn.commit()