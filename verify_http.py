"""
verify_http.py - Prueba el servidor HTTP completo mediante solicitudes HTTP reales.
"""

import threading
import time
import urllib.request
import urllib.parse
import json
from http.server import ThreadingHTTPServer

from server import AgendaRequestHandler
from database import init_db, get_config

def run():
    init_db()
    PORT = 5099
    server = ThreadingHTTPServer(("127.0.0.1", PORT), AgendaRequestHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.5)

    base_url = f"http://127.0.0.1:{PORT}"

    try:
        # 1. Test index.html
        with urllib.request.urlopen(f"{base_url}/") as res:
            assert res.status == 200
            content = res.read().decode("utf-8")
            assert "Agenda tu Turno" in content
            print("✓ GET / (index.html) -> 200 OK")

        # 2. Test admin.html
        with urllib.request.urlopen(f"{base_url}/admin") as res:
            assert res.status == 200
            content = res.read().decode("utf-8")
            assert "Panel Administrador" in content
            print("✓ GET /admin (admin.html) -> 200 OK")

        # 3. Test /api/config
        with urllib.request.urlopen(f"{base_url}/api/config") as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert "titulo_agenda" in data
            print("✓ GET /api/config -> 200 OK")

        # 4. Test /api/slots
        with urllib.request.urlopen(f"{base_url}/api/slots?date=2026-11-18") as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["disponible"] is True
            print("✓ GET /api/slots -> 200 OK")

        # 5. Test POST /api/turnos
        booking_payload = {
            "nombre": "Ana",
            "apellido": "Martínez",
            "celular": "+54 9 11 4444-8888",
            "motivo": "Turno de prueba HTTP",
            "fecha": "2026-11-18",
            "hora_inicio": "11:00",
            "hora_fin": "11:45"
        }
        req = urllib.request.Request(
            f"{base_url}/api/turnos",
            data=json.dumps(booking_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req) as res:
            assert res.status == 201
            resp_data = json.loads(res.read().decode("utf-8"))
            turno_id = resp_data["turno"]["id"]
            print(f"✓ POST /api/turnos -> 201 Created (ID: {turno_id})")

        # 6. Test Feed iCalendar
        cfg = get_config()
        token = cfg["calendar_token"]
        feed_url = f"{base_url}/api/calendar/apple.ics?token={token}"
        with urllib.request.urlopen(feed_url) as res:
            assert res.status == 200
            assert "text/calendar" in res.headers.get("Content-Type")
            feed_text = res.read().decode("utf-8")
            assert "Turno: Ana Martínez" in feed_text
            assert "BEGIN:VALARM" in feed_text
            print("✓ GET /api/calendar/apple.ics (Apple Calendar Feed) -> 200 OK (iCalendar verificado)")

        # 7. Test Single Event download
        single_ics_url = f"{base_url}/api/calendar/download/{turno_id}.ics"
        with urllib.request.urlopen(single_ics_url) as res:
            assert res.status == 200
            single_text = res.read().decode("utf-8")
            assert "BEGIN:VCALENDAR" in single_text
            print(f"✓ GET /api/calendar/download/{turno_id}.ics -> 200 OK")

        print("\n" + "="*50)
        print(" 🎉 VERIFICACIÓN HTTP COMPLETA EXITOSA")
        print("="*50)

    finally:
        server.shutdown()
        server.server_close()

if __name__ == "__main__":
    run()
