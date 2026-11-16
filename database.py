"""
database.py - Módulo de base de datos SQLite para la Agenda de Turnos.
Maneja turnos, configuración del profesional y franjas bloqueadas.
"""

import sqlite3
import os
import json
import secrets
from datetime import datetime

DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "agenda.db"))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla de turnos
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS turnos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        apellido TEXT NOT NULL,
        celular TEXT NOT NULL,
        email TEXT DEFAULT '',
        motivo TEXT DEFAULT '',
        fecha TEXT NOT NULL,          -- Formato YYYY-MM-DD
        hora_inicio TEXT NOT NULL,    -- Formato HH:MM
        hora_fin TEXT NOT NULL,       -- Formato HH:MM
        estado TEXT DEFAULT 'confirmado', -- 'confirmado', 'cancelado', 'completado'
        creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Tabla de configuración
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS configuracion (
        clave TEXT PRIMARY KEY,
        valor TEXT NOT NULL
    );
    """)

    # Tabla de bloqueos o feriados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bloqueos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT NOT NULL,
        hora_inicio TEXT DEFAULT '',
        hora_fin TEXT DEFAULT '',
        motivo TEXT DEFAULT 'No disponible'
    );
    """)

    # Valores por defecto de configuración
    defaults = {
        "titulo_agenda": "Agenda de Turnos",
        "descripcion_agenda": "Selecciona el día y la hora que mejor te quede para coordinar tu cita.",
        "nombre_profesional": "Administrador",
        "telefono_contacto": "+54 9 11 0000-0000",
        "duracion_minutos": "45",
        "buffer_minutos": "15",
        "dias_laborales": json.dumps([1, 2, 3, 4, 5]), # 0=Domingo, 1=Lunes, ..., 6=Sábado
        "hora_apertura": "09:00",
        "hora_cierre": "18:00",
        "pausa_inicio": "13:00",
        "pausa_fin": "14:00",
        "admin_password": "admin", # Clave inicial, modificable desde el panel
        "calendar_token": secrets.token_hex(16),
        "dias_anticipacion_max": "30"
    }

    for key, val in defaults.items():
        cursor.execute("INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()

def get_config():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT clave, valor FROM configuracion")
    rows = cursor.fetchall()
    conn.close()
    cfg = {}
    for r in rows:
        key = r["clave"]
        val = r["valor"]
        if key == "dias_laborales":
            try:
                cfg[key] = json.loads(val)
            except Exception:
                cfg[key] = [1, 2, 3, 4, 5]
        elif key in ("duracion_minutos", "buffer_minutos", "dias_anticipacion_max"):
            try:
                cfg[key] = int(val)
            except Exception:
                cfg[key] = 30
        else:
            cfg[key] = val
    return cfg

def update_config(data: dict):
    conn = get_connection()
    cursor = conn.cursor()
    for key, val in data.items():
        if key == "dias_laborales" and isinstance(val, list):
            val = json.dumps(val)
        else:
            val = str(val)
        cursor.execute("""
            INSERT INTO configuracion (clave, valor) VALUES (?, ?)
            ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor
        """, (key, val))
    conn.commit()
    conn.close()

def get_turnos(filtro_estado=None, fecha=None, desde_fecha=None):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM turnos WHERE 1=1"
    params = []

    if filtro_estado:
        query += " AND estado = ?"
        params.append(filtro_estado)
    if fecha:
        query += " AND fecha = ?"
        params.append(fecha)
    if desde_fecha:
        query += " AND fecha >= ?"
        params.append(desde_fecha)

    query += " ORDER BY fecha ASC, hora_inicio ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_turno_by_id(turno_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM turnos WHERE id = ?", (turno_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def crear_turno(nombre, apellido, celular, email, motivo, fecha, hora_inicio, hora_fin):
    conn = get_connection()
    cursor = conn.cursor()

    # Verificar si el horario ya está ocupado
    cursor.execute("""
        SELECT id FROM turnos 
        WHERE fecha = ? AND hora_inicio = ? AND estado != 'cancelado'
    """, (fecha, hora_inicio))
    if cursor.fetchone():
        conn.close()
        return None, "El horario seleccionado ya no se encuentra disponible. Por favor elige otro."

    cursor.execute("""
        INSERT INTO turnos (nombre, apellido, celular, email, motivo, fecha, hora_inicio, hora_fin, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'confirmado')
    """, (nombre.strip(), apellido.strip(), celular.strip(), email.strip(), motivo.strip(), fecha, hora_inicio, hora_fin))
    
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id, None

def actualizar_estado_turno(turno_id, nuevo_estado):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE turnos SET estado = ? WHERE id = ?", (nuevo_estado, turno_id))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def eliminar_turno(turno_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM turnos WHERE id = ?", (turno_id,))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0

def export_turnos_csv():
    import csv
    import io
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, apellido, celular, email, motivo, fecha, hora_inicio, hora_fin, estado, creado_en FROM turnos ORDER BY fecha DESC, hora_inicio DESC")
    rows = cursor.fetchall()
    conn.close()

    output = io.StringIO()
    output.write("\ufeff") # BOM UTF-8 para Excel
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Nombre", "Apellido", "Celular / WhatsApp", "Email", "Motivo", "Fecha", "Hora Inicio", "Hora Fin", "Estado", "Fecha Registro"])
    for r in rows:
        writer.writerow([
            r["id"], r["nombre"], r["apellido"], r["celular"], 
            r["email"], r["motivo"], r["fecha"], r["hora_inicio"], 
            r["hora_fin"], r["estado"], r["creado_en"]
        ])
    return output.getvalue().encode("utf-8")

