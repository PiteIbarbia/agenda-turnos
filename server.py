"""
server.py - Servidor HTTP principal multihilo para la Agenda de Turnos.
Incluye API REST, entrega de archivos estáticos y Feed iCalendar para Apple Calendar.
Sin dependencias externas (utiliza únicamente la librería estándar de Python).
"""

import os
import sys
import json
import socket
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime

from database import (
    init_db, get_config, update_config, get_turnos, 
    get_turno_by_id, crear_turno, actualizar_estado_turno, eliminar_turno
)
from slot_calculator import get_available_slots
from calendar_feed import generate_ical_feed, generate_single_event_ics

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Sesiones de admin en memoria (token -> timestamp)
ADMIN_SESSIONS = set()

def get_local_ip():
    """Detecta la IP local en la red Wi-Fi/LAN para permitir acceso desde celulares/tablets."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

class AgendaRequestHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Log simplificado para no saturar la consola
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]} {args[1]}\n")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PATCH, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": True, "mensaje": message}, status=status)

    def is_admin_authenticated(self):
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token in ADMIN_SESSIONS:
                return True
        # Alternativamente por cookie o parámetro query
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        token = qs.get("token", [""])[0]
        if token and token in ADMIN_SESSIONS:
            return True
        return False

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. Feed iCalendar para Apple Calendar
        if path == "/api/calendar/apple.ics":
            token = qs.get("token", [""])[0]
            cfg = get_config()
            expected_token = cfg.get("calendar_token", "")
            
            if not token or token != expected_token:
                self.send_response(401)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"Acceso no autorizado al calendario.")
                return

            turnos = get_turnos()
            cal_name = cfg.get("titulo_agenda", "Agenda de Turnos")
            ics_content = generate_ical_feed(turnos, calendar_name=cal_name)
            ics_bytes = ics_content.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", 'inline; filename="agenda_turnos.ics"')
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(ics_bytes)))
            self.end_headers()
            self.wfile.write(ics_bytes)
            return

        # 2. Descarga de .ics individual para el cliente
        if path.startswith("/api/calendar/download/"):
            try:
                turno_id = int(path.split("/")[-1].replace(".ics", ""))
                turno = get_turno_by_id(turno_id)
                if not turno:
                    self.send_error_json("Turno no encontrado", 404)
                    return
                cfg = get_config()
                ics_data = generate_single_event_ics(turno, business_name=cfg.get("titulo_agenda", "Agenda"))
                ics_bytes = ics_data.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/calendar; charset=utf-8")
                self.send_header("Content-Disposition", f'attachment; filename="turno_{turno_id}.ics"')
                self.send_header("Content-Length", str(len(ics_bytes)))
                self.end_headers()
                self.wfile.write(ics_bytes)
                return
            except Exception as e:
                self.send_error_json(f"Error generando archivo: {str(e)}", 400)
                return

        # 3. API Configuración Pública
        if path == "/api/config":
            cfg = get_config()
            # Ocultamos la clave de admin
            safe_cfg = {
                "titulo_agenda": cfg.get("titulo_agenda", "Agenda de Turnos"),
                "descripcion_agenda": cfg.get("descripcion_agenda", ""),
                "nombre_profesional": cfg.get("nombre_profesional", ""),
                "telefono_contacto": cfg.get("telefono_contacto", ""),
                "duracion_minutos": cfg.get("duracion_minutos", 45),
                "dias_laborales": cfg.get("dias_laborales", [1, 2, 3, 4, 5]),
                "hora_apertura": cfg.get("hora_apertura", "09:00"),
                "hora_cierre": cfg.get("hora_cierre", "18:00"),
                "dias_anticipacion_max": cfg.get("dias_anticipacion_max", 30)
            }
            self.send_json(safe_cfg)
            return

        # 4. API Horarios disponibles por fecha
        if path == "/api/slots":
            fecha = qs.get("date", [""])[0]
            if not fecha:
                self.send_error_json("Parámetro 'date' requerido (YYYY-MM-DD)")
                return
            result = get_available_slots(fecha)
            self.send_json(result)
            return

        # 5. API Admin: Obtener configuración completa
        if path == "/api/admin/config":
            if not self.is_admin_authenticated():
                self.send_error_json("No autorizado", 401)
                return
            cfg = get_config()
            cfg_safe = dict(cfg)
            # Reemplazar contraseña por flag para no exponerla en texto plano
            cfg_safe["admin_password_set"] = bool(cfg.get("admin_password"))
            cfg_safe.pop("admin_password", None)
            
            # Construir URL para Apple Calendar
            host = self.headers.get("Host", f"localhost:{self.server.server_port}")
            token = cfg.get("calendar_token", "")
            cfg_safe["apple_calendar_webcal_url"] = f"webcal://{host}/api/calendar/apple.ics?token={token}"
            cfg_safe["apple_calendar_https_url"] = f"http://{host}/api/calendar/apple.ics?token={token}"
            self.send_json(cfg_safe)
            return

        # 6. API Admin: Listar turnos
        if path == "/api/admin/turnos":
            if not self.is_admin_authenticated():
                self.send_error_json("No autorizado", 401)
                return
            filtro_estado = qs.get("estado", [None])[0]
            fecha = qs.get("fecha", [None])[0]
            desde_fecha = qs.get("desde", [None])[0]
            turnos = get_turnos(filtro_estado=filtro_estado, fecha=fecha, desde_fecha=desde_fecha)
            self.send_json({"turnos": turnos, "total": len(turnos)})
            return

        # 7. Servir archivos estáticos y páginas HTML
        self.serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        
        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            self.send_error_json("JSON inválido", 400)
            return

        # 1. Login Admin
        if path == "/api/admin/login":
            password = payload.get("password", "")
            cfg = get_config()
            if password == cfg.get("admin_password", "admin"):
                import secrets
                token = secrets.token_hex(24)
                ADMIN_SESSIONS.add(token)
                self.send_json({"ok": True, "token": token, "mensaje": "Autenticación exitosa"})
            else:
                self.send_error_json("Contraseña incorrecta", 401)
            return

        # 2. Crear turno (Cliente)
        if path == "/api/turnos":
            nombre = payload.get("nombre", "").strip()
            apellido = payload.get("apellido", "").strip()
            celular = payload.get("celular", "").strip()
            email = payload.get("email", "").strip()
            motivo = payload.get("motivo", "").strip()
            fecha = payload.get("fecha", "").strip()
            hora_inicio = payload.get("hora_inicio", "").strip()
            hora_fin = payload.get("hora_fin", "").strip()

            # Validación de campos obligatorios
            errores = []
            if not nombre:
                errores.append("El nombre es obligatorio.")
            if not apellido:
                errores.append("El apellido es obligatorio.")
            if not celular:
                errores.append("El número de celular/WhatsApp es obligatorio.")
            if not fecha or not hora_inicio or not hora_fin:
                errores.append("Debes seleccionar una fecha y horario disponible.")

            if errores:
                self.send_error_json(" ".join(errores), 400)
                return

            new_id, err = crear_turno(nombre, apellido, celular, email, motivo, fecha, hora_inicio, hora_fin)
            if err:
                self.send_error_json(err, 409)
                return

            cfg = get_config()
            turno_data = get_turno_by_id(new_id)
            self.send_json({
                "ok": True,
                "mensaje": "¡Tu turno ha sido confirmado con éxito!",
                "turno": turno_data,
                "ics_download_url": f"/api/calendar/download/{new_id}.ics"
            }, 201)
            return

        # 3. Guardar configuración de admin
        if path == "/api/admin/config":
            if not self.is_admin_authenticated():
                self.send_error_json("No autorizado", 401)
                return
            
            # Si se pasa una nueva contraseña, actualizarla
            nueva_pass = payload.get("new_password", "").strip()
            updates = {k: v for k, v in payload.items() if k != "new_password"}
            if nueva_pass:
                updates["admin_password"] = nueva_pass

            update_config(updates)
            self.send_json({"ok": True, "mensaje": "Configuración actualizada correctamente"})
            return

        # 4. Actualizar estado de turno (Admin)
        if path == "/api/admin/turnos/status":
            if not self.is_admin_authenticated():
                self.send_error_json("No autorizado", 401)
                return
            turno_id = payload.get("id")
            nuevo_estado = payload.get("estado")
            if not turno_id or nuevo_estado not in ("confirmado", "cancelado", "completado"):
                self.send_error_json("Parámetros inválidos", 400)
                return
            ok = actualizar_estado_turno(turno_id, nuevo_estado)
            if ok:
                self.send_json({"ok": True, "mensaje": f"Turno #{turno_id} actualizado a '{nuevo_estado}'"})
            else:
                self.send_error_json("Turno no encontrado", 404)
            return

        # 5. Eliminar turno (Admin)
        if path == "/api/admin/turnos/delete":
            if not self.is_admin_authenticated():
                self.send_error_json("No autorizado", 401)
                return
            turno_id = payload.get("id")
            if not turno_id:
                self.send_error_json("ID de turno requerido", 400)
                return
            ok = eliminar_turno(turno_id)
            if ok:
                self.send_json({"ok": True, "mensaje": f"Turno #{turno_id} eliminado"})
            else:
                self.send_error_json("Turno no encontrado", 404)
            return

        self.send_error_json("Ruta no encontrada", 404)

    def serve_static(self, path):
        # Mapeos por defecto
        if path in ("", "/"):
            file_path = os.path.join(STATIC_DIR, "index.html")
        elif path in ("/admin", "/admin/"):
            file_path = os.path.join(STATIC_DIR, "admin.html")
        else:
            rel_path = path.lstrip("/")
            file_path = os.path.join(STATIC_DIR, rel_path)

        if not os.path.exists(file_path) or os.path.isdir(file_path):
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h1>404 - Pagina no encontrada</h1>")
            return

        # Detectar tipo MIME
        mime_types = {
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
        ext = os.path.splitext(file_path)[1].lower()
        content_type = mime_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error al leer archivo: {e}".encode("utf-8"))

def run_server(port=5000):
    init_db()
    local_ip = get_local_ip()
    
    server_address = ("0.0.0.0", port)
    httpd = ThreadingHTTPServer(server_address, AgendaRequestHandler)
    
    cfg = get_config()
    token = cfg.get("calendar_token", "")
    
    print("=" * 65)
    print(" 🚀 SERVIDOR DE AGENDA DE TURNOS INICIADO")
    print("=" * 65)
    print(f" • Acceso Cliente (Local):     http://localhost:{port}")
    print(f" • Acceso Cliente (Red Wi-Fi): http://{local_ip}:{port}")
    print(f" • Panel de Administración:    http://localhost:{port}/admin")
    print(f" • Clave inicial de Admin:     {cfg.get('admin_password', 'admin')}")
    print("-" * 65)
    print(" 📅 SINCRONIZACIÓN APPLE CALENDAR (WebCal Feed):")
    print(f" • URL WebCal (iPhone/Mac):    webcal://{local_ip}:{port}/api/calendar/apple.ics?token={token}")
    print(f" • URL HTTP:                   http://{local_ip}:{port}/api/calendar/apple.ics?token={token}")
    print("=" * 65)
    print(" Presiona Ctrl + C para detener el servidor.\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        httpd.server_close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    run_server(port)
