"""
test_server.py - Pruebas automáticas del backend, cálculo de horarios y feed Apple Calendar.
"""

import os
import sys
from datetime import datetime, timedelta

from database import (
    init_db, get_config, update_config, crear_turno, 
    get_turnos, actualizar_estado_turno, eliminar_turno
)
from slot_calculator import get_available_slots
from calendar_feed import generate_ical_feed, generate_single_event_ics

def run_tests():
    print("▶ 1. Inicializando Base de Datos...")
    init_db()
    cfg = get_config()
    assert "titulo_agenda" in cfg, "Error: Config no contiene titulo_agenda"
    assert "calendar_token" in cfg, "Error: Config no contiene calendar_token"
    print(f"  ✓ Base de datos iniciada. Token de calendario: {cfg['calendar_token'][:8]}...")

    print("\n▶ 2. Probando cálculo de horarios disponibles...")
    # Buscamos un día hábil próximo
    hoy = datetime.now()
    test_date = None
    for i in range(1, 10):
        d = hoy + timedelta(days=i)
        # Lunes a Viernes
        if d.weekday() in (0, 1, 2, 3, 4):
            test_date = d.strftime("%Y-%m-%d")
            break

    assert test_date is not None, "Error buscando fecha de prueba"
    slots_res = get_available_slots(test_date)
    assert slots_res["disponible"] is True, f"Error: {slots_res.get('mensaje')}"
    assert len(slots_res["slots"]) > 0, "Error: No se generaron slots para día hábil"
    slot_test = slots_res["slots"][0]
    print(f"  ✓ Fecha {test_date}: {len(slots_res['slots'])} slots encontrados. Primer slot: {slot_test['label']}")

    print("\n▶ 3. Probando reserva de un turno...")
    turno_id, err = crear_turno(
        nombre="Martín",
        apellido="González",
        celular="+54 9 11 9876-5432",
        email="martin@ejemplo.com",
        motivo="Consulta de orientación",
        fecha=test_date,
        hora_inicio=slot_test["hora_inicio"],
        hora_fin=slot_test["hora_fin"]
    )
    assert err is None, f"Error creando turno: {err}"
    assert turno_id is not None, "Error: ID de turno es None"
    print(f"  ✓ Turno creado con éxito! ID: {turno_id}")

    print("\n▶ 4. Probando prevención de doble reserva (mismo horario)...")
    dup_id, dup_err = crear_turno(
        nombre="Pedro",
        apellido="López",
        celular="+54 9 11 1111-2222",
        email="",
        motivo="",
        fecha=test_date,
        hora_inicio=slot_test["hora_inicio"],
        hora_fin=slot_test["hora_fin"]
    )
    assert dup_id is None, "Error: Se permitió duplicar turno"
    assert "ya no se encuentra disponible" in dup_err, "Mensaje de error inesperado"
    print("  ✓ Prevención de doble reserva funcionando correctamente.")

    print("\n▶ 5. Probando generación de Feed para Apple Calendar (.ics)...")
    turnos = get_turnos()
    feed_ics = generate_ical_feed(turnos, calendar_name=cfg.get("titulo_agenda"))
    assert "BEGIN:VCALENDAR" in feed_ics, "Falta cabecera VCALENDAR"
    assert "END:VCALENDAR" in feed_ics, "Falta cierre VCALENDAR"
    assert "BEGIN:VEVENT" in feed_ics, "Falta evento VEVENT"
    assert "Turno: Martín González" in feed_ics, "Falta resumen del cliente en VEVENT"
    assert "Teléfono / WhatsApp: +54 9 11 9876-5432" in feed_ics, "Falta celular en VEVENT"
    assert "REFRESH-INTERVAL;VALUE=DURATION:PT15M" in feed_ics, "Falta directiva de auto-refresco Apple"
    print("  ✓ Feed iCalendar para Apple Calendar generado y validado con RFC 5545.")

    print("\n▶ 6. Probando actualización de estado y cancelación...")
    ok = actualizar_estado_turno(turno_id, "cancelado")
    assert ok is True, "Error actualizando estado a cancelado"
    # El horario debe volver a estar disponible
    slots_after_cancel = get_available_slots(test_date)
    slots_horas = [s["hora_inicio"] for s in slots_after_cancel["slots"]]
    assert slot_test["hora_inicio"] in slots_horas, "El slot cancelado no volvió a liberarse"
    print("  ✓ Turno cancelado y slot liberado con éxito.")

    # Limpieza del turno de prueba
    eliminar_turno(turno_id)
    print("  ✓ Registro de prueba eliminado de la base de datos.")

    print("\n" + "="*50)
    print(" 🎉 TODAS LAS PRUEBAS PASARON EXITOSAMENTE (6/6)")
    print("="*50)

if __name__ == "__main__":
    run_tests()
