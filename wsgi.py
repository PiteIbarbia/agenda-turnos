"""
wsgi.py - Interfaz WSGI estándar para despliegue en PythonAnywhere y servidores WSGI.
Permite servir la API, las páginas estáticas y el feed de Apple Calendar sin dependencias externas.
"""

import os
import sys
import json
import urllib.parse
from datetime import datetime

# Asegurar que el directorio del proyecto esté en sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

STATIC_DIR = os.path.join(BASE_DIR, "static")

from database import (
    init_db, get_config, update_config, get_turnos,
    get_turno_by_id, crear_turno, actualizar_estado_turno, eliminar_turno
)
from slot_calculator import get_available_slots
from calendar_feed import generate_ical_feed, generate_single_event_ics

# Inicializar base de datos
init_db()

# Sesiones de administrador en memoria
ADMIN_SESSIONS = set()

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".ics": "text/calendar; charset=utf-8"
}

def application(environ, start_response):
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET").upper()
    qs_string = environ.get("QUERY_STRING", "")
    qs = urllib.parse.parse_qs(qs_string)

    # Headers de ayuda
    def json_response(data, status_code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        status = f"{status_code} OK" if status_code == 200 else f"{status_code} Error"
        if status_code == 201: status = "201 Created"
        if status_code == 400: status = "400 Bad Request"
        if status_code == 401: status = "401 Unauthorized"
        if status_code == 404: status = "404 Not Found"
        if status_code == 409: status = "409 Conflict"
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PATCH, DELETE"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization")
        ]
        start_response(status, headers)
        return [body]

    def is_auth():
        auth_header = environ.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token in ADMIN_SESSIONS:
                return True
        token_q = qs.get("token", [""])[0]
        if token_q and token_q in ADMIN_SESSIONS:
            return True
        return False

    # Manejo de OPTIONS para CORS
    if method == "OPTIONS":
        start_response("200 OK", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type, Authorization"),
            ("Content-Length", "0")
        ])
        return [b""]

    # --- RUTAS GET ---
    if method == "GET":
        # 1. Feed Apple Calendar (.ics)
        if path == "/api/calendar/apple.ics":
            token = qs.get("token", [""])[0]
            cfg = get_config()
            expected_token = cfg.get("calendar_token", "")
            if not token or token != expected_token:
                start_response("401 Unauthorized", [("Content-Type", "text/plain; charset=utf-8")])
                return [b"Acceso no autorizado al calendario."]
            
            turnos = get_turnos()
            cal_name = cfg.get("titulo_agenda", "Agenda de Turnos")
            ics_content = generate_ical_feed(turnos, calendar_name=cal_name)
            ics_bytes = ics_content.encode("utf-8")
            start_response("200 OK", [
                ("Content-Type", "text/calendar; charset=utf-8"),
                ("Content-Disposition", 'inline; filename="agenda_turnos.ics"'),
                ("Cache-Control", "no-cache, no-store, must-revalidate"),
                ("Content-Length", str(len(ics_bytes)))
            ])
            return [ics_bytes]

        # 2. Descarga individual .ics para cliente
        if path.startswith("/api/calendar/download/"):
            try:
                turno_id = int(path.split("/")[-1].replace(".ics", ""))
                turno = get_turno_by_id(turno_id)
                if not turno:
                    return json_response({"error": True, "mensaje": "Turno no encontrado"}, 404)
                cfg = get_config()
                ics_data = generate_single_event_ics(turno, business_name=cfg.get("titulo_agenda", "Agenda"))
                ics_bytes = ics_data.encode("utf-8")
                start_response("200 OK", [
                    ("Content-Type", "text/calendar; charset=utf-8"),
                    ("Content-Disposition", f'attachment; filename="turno_{turno_id}.ics"'),
                    ("Content-Length", str(len(ics_bytes)))
                ])
                return [ics_bytes]
            except Exception as e:
                return json_response({"error": True, "mensaje": str(e)}, 400)

        # 3. Configuración pública
        if path == "/api/config":
            cfg = get_config()
            return json_response({
                "titulo_agenda": cfg.get("titulo_agenda", "Agenda de Turnos"),
                "descripcion_agenda": cfg.get("descripcion_agenda", ""),
                "nombre_profesional": cfg.get("nombre_profesional", ""),
                "telefono_contacto": cfg.get("telefono_contacto", ""),
                "duracion_minutos": cfg.get("duracion_minutos", 45),
                "dias_laborales": cfg.get("dias_laborales", [1, 2, 3, 4, 5]),
                "hora_apertura": cfg.get("hora_apertura", "09:00"),
                "hora_cierre": cfg.get("hora_cierre", "18:00"),
                "dias_anticipacion_max": cfg.get("dias_anticipacion_max", 30)
            })

        # 4. Horarios disponibles
        if path == "/api/slots":
            fecha = qs.get("date", [""])[0]
            if not fecha:
                return json_response({"error": True, "mensaje": "Fecha requerida"}, 400)
            result = get_available_slots(fecha)
            return json_response(result)

        # 5. Configuración Admin
        if path == "/api/admin/config":
            if not is_auth():
                return json_response({"error": True, "mensaje": "No autorizado"}, 401)
            cfg = get_config()
            cfg_safe = dict(cfg)
            cfg_safe["admin_password_set"] = bool(cfg.get("admin_password"))
            cfg_safe.pop("admin_password", None)
            host = environ.get("HTTP_HOST", "localhost")
            token = cfg.get("calendar_token", "")
            cfg_safe["apple_calendar_webcal_url"] = f"webcal://{host}/api/calendar/apple.ics?token={token}"
            cfg_safe["apple_calendar_https_url"] = f"https://{host}/api/calendar/apple.ics?token={token}"
            return json_response(cfg_safe)

        # 6. Turnos Admin
        if path == "/api/admin/turnos":
            if not is_auth():
                return json_response({"error": True, "mensaje": "No autorizado"}, 401)
            filtro_estado = qs.get("estado", [None])[0]
            fecha = qs.get("fecha", [None])[0]
            desde_fecha = qs.get("desde", [None])[0]
            turnos = get_turnos(filtro_estado=filtro_estado, fecha=fecha, desde_fecha=desde_fecha)
            return json_response({"turnos": turnos, "total": len(turnos)})

        # 7. Servir archivos estáticos
        target_path = None
        if path in ("", "/"):
            target_path = os.path.join(STATIC_DIR, "index.html")
        elif path in ("/admin", "/admin/"):
            target_path = os.path.join(STATIC_DIR, "admin.html")
        elif path.startswith("/static/"):
            rel_file = path.replace("/static/", "", 1)
            target_path = os.path.join(STATIC_DIR, rel_file)

        if target_path and os.path.exists(target_path) and not os.path.isdir(target_path):
            ext = os.path.splitext(target_path)[1].lower()
            content_type = MIME_TYPES.get(ext, "application/octet-stream")
            with open(target_path, "rb") as f:
                content = f.read()
            start_response("200 OK", [
                ("Content-Type", content_type),
                ("Content-Length", str(len(content)))
            ])
            return [content]

    # --- RUTAS POST ---
    if method == "POST":
        content_length = int(environ.get("CONTENT_LENGTH", 0) or 0)
        post_data = environ.get("wsgi.input").read(content_length) if content_length > 0 else b""
        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            return json_response({"error": True, "mensaje": "JSON inválido"}, 400)

        # 1. Login Admin
        if path == "/api/admin/login":
            password = payload.get("password", "")
            cfg = get_config()
            if password == cfg.get("admin_password", "admin"):
                import secrets
                token = secrets.token_hex(24)
                ADMIN_SESSIONS.add(token)
                return json_response({"ok": True, "token": token, "mensaje": "Autenticación exitosa"})
            return json_response({"error": True, "mensaje": "Contraseña incorrecta"}, 401)

        # 2. Crear Turno
        if path == "/api/turnos":
            nombre = payload.get("nombre", "").strip()
            apellido = payload.get("apellido", "").strip()
            celular = payload.get("celular", "").strip()
            email = payload.get("email", "").strip()
            motivo = payload.get("motivo", "").strip()
            fecha = payload.get("fecha", "").strip()
            hora_inicio = payload.get("hora_inicio", "").strip()
            hora_fin = payload.get("hora_fin", "").strip()

            errores = []
            if not nombre: errores.append("El nombre es obligatorio.")
            if not apellido: errores.append("El apellido es obligatorio.")
            if not celular: errores.append("El celular es obligatorio.")
            if not fecha or not hora_inicio or not hora_fin: errores.append("Fecha y hora requeridas.")

            if errores:
                return json_response({"error": True, "mensaje": " ".join(errores)}, 400)

            new_id, err = crear_turno(nombre, apellido, celular, email, motivo, fecha, hora_inicio, hora_fin)
            if err:
                return json_response({"error": True, "mensaje": err}, 409)

            turno_data = get_turno_by_id(new_id)
            return json_response({
                "ok": True,
                "mensaje": "¡Tu turno ha sido confirmado con éxito!",
                "turno": turno_data,
                "ics_download_url": f"/api/calendar/download/{new_id}.ics"
            }, 201)

        # 3. Guardar Configuración Admin
        if path == "/api/admin/config":
            if not is_auth():
                return json_response({"error": True, "mensaje": "No autorizado"}, 401)
            nueva_pass = payload.get("new_password", "").strip()
            updates = {k: v for k, v in payload.items() if k != "new_password"}
            if nueva_pass:
                updates["admin_password"] = nueva_pass
            update_config(updates)
            return json_response({"ok": True, "mensaje": "Configuración guardada correctamente"})

        # 4. Actualizar Estado de Turno
        if path == "/api/admin/turnos/status":
            if not is_auth():
                return json_response({"error": True, "mensaje": "No autorizado"}, 401)
            turno_id = payload.get("id")
            nuevo_estado = payload.get("estado")
            ok = actualizar_estado_turno(turno_id, nuevo_estado)
            if ok:
                return json_response({"ok": True, "mensaje": f"Turno #{turno_id} actualizado"})
            return json_response({"error": True, "mensaje": "Turno no encontrado"}, 404)

        # 5. Eliminar Turno
        if path == "/api/admin/turnos/delete":
            if not is_auth():
                return json_response({"error": True, "mensaje": "No autorizado"}, 401)
            turno_id = payload.get("id")
            ok = eliminar_turno(turno_id)
            if ok:
                return json_response({"ok": True, "mensaje": f"Turno #{turno_id} eliminado"})
            return json_response({"error": True, "mensaje": "Turno no encontrado"}, 404)

    # 404 por defecto
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"404 - Ruta no encontrada"]
