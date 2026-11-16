"""
slot_calculator.py - Calcula los horarios disponibles para reserva
en base a la configuración de trabajo y turnos ya agendados.
"""

from datetime import datetime, timedelta, time
import json
from database import get_config, get_turnos, get_connection

def parse_time_str(t_str: str) -> time:
    parts = t_str.split(":")
    return time(int(parts[0]), int(parts[1]))

def format_time_str(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def get_available_slots(fecha_str: str) -> dict:
    """
    Retorna un diccionario con:
    - disponible: bool (si el día está habilitado para atención)
    - mensaje: str (motivo si no está disponible)
    - slots: lista de {'hora_inicio': '09:00', 'hora_fin': '09:45'}
    """
    try:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
    except ValueError:
        return {"disponible": False, "mensaje": "Fecha inválida", "slots": []}

    hoy = datetime.now().date()
    ahora = datetime.now()

    if fecha_obj < hoy:
        return {"disponible": False, "mensaje": "No se pueden solicitar turnos en fechas pasadas.", "slots": []}

    cfg = get_config()
    dias_laborales = cfg.get("dias_laborales", [1, 2, 3, 4, 5])
    
    # Python weekday(): Lunes=0, Domingo=6.
    # Convertimos a formato: Domingo=0, Lunes=1, ..., Sábado=6
    weekday_standard = (fecha_obj.weekday() + 1) % 7
    if weekday_standard not in dias_laborales:
        return {"disponible": False, "mensaje": "El profesional no atiende en el día seleccionado.", "slots": []}

    # Verificar rango de anticipación máxima
    max_dias = cfg.get("dias_anticipacion_max", 30)
    if (fecha_obj - hoy).days > max_dias:
        return {"disponible": False, "mensaje": f"Solo se pueden agendar turnos con hasta {max_dias} días de anticipación.", "slots": []}

    # Horarios de apertura y cierre
    h_apertura = parse_time_str(cfg.get("hora_apertura", "09:00"))
    h_cierre = parse_time_str(cfg.get("hora_cierre", "18:00"))
    h_pausa_ini = parse_time_str(cfg.get("pausa_inicio", "13:00")) if cfg.get("pausa_inicio") else None
    h_pausa_fin = parse_time_str(cfg.get("pausa_fin", "14:00")) if cfg.get("pausa_fin") else None

    duracion = int(cfg.get("duracion_minutos", 45))
    buffer_min = int(cfg.get("buffer_minutos", 15))
    paso = duracion + buffer_min

    # Turnos ocupados para esta fecha
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT hora_inicio, hora_fin FROM turnos 
        WHERE fecha = ? AND estado != 'cancelado'
    """, (fecha_str,))
    turnos_ocupados = set(row["hora_inicio"] for row in c.fetchall())

    # Bloqueos generales del día
    c.execute("SELECT hora_inicio, hora_fin FROM bloqueos WHERE fecha = ?", (fecha_str,))
    bloqueos = c.fetchall()
    conn.close()

    slots_disponibles = []
    
    dt_cursor = datetime.combine(fecha_obj, h_apertura)
    dt_fin_jornada = datetime.combine(fecha_obj, h_cierre)
    delta_duracion = timedelta(minutes=duracion)
    delta_paso = timedelta(minutes=paso)

    while dt_cursor + delta_duracion <= dt_fin_jornada:
        dt_slot_inicio = dt_cursor
        dt_slot_fin = dt_cursor + delta_duracion

        h_ini_str = format_time_str(dt_slot_inicio)
        h_fin_str = format_time_str(dt_slot_fin)

        # Si es el día de hoy, descartar horarios pasados con margen de 30 mins
        if fecha_obj == hoy and dt_slot_inicio <= (ahora + timedelta(minutes=15)):
            dt_cursor += delta_paso
            continue

        # Verificar si cae dentro de la pausa de almuerzo/descanso
        dentro_pausa = False
        if h_pausa_ini and h_pausa_fin:
            dt_pausa_ini = datetime.combine(fecha_obj, h_pausa_ini)
            dt_pausa_fin = datetime.combine(fecha_obj, h_pausa_fin)
            # Solapamiento
            if not (dt_slot_fin <= dt_pausa_ini or dt_slot_inicio >= dt_pausa_fin):
                dentro_pausa = True

        if dentro_pausa:
            dt_cursor += delta_paso
            continue

        # Verificar si el turno ya fue tomado
        if h_ini_str in turnos_ocupados:
            dt_cursor += delta_paso
            continue

        # Verificar bloqueos manuales
        bloqueado = False
        for b in bloqueos:
            b_ini = b["hora_inicio"]
            b_fin = b["hora_fin"]
            if not b_ini and not b_fin: # Todo el día bloqueado
                bloqueado = True
                break
            if b_ini and b_fin:
                dt_b_ini = datetime.combine(fecha_obj, parse_time_str(b_ini))
                dt_b_fin = datetime.combine(fecha_obj, parse_time_str(b_fin))
                if not (dt_slot_fin <= dt_b_ini or dt_slot_inicio >= dt_b_fin):
                    bloqueado = True
                    break

        if not bloqueado:
            slots_disponibles.append({
                "hora_inicio": h_ini_str,
                "hora_fin": h_fin_str,
                "label": f"{h_ini_str} a {h_fin_str}"
            })

        dt_cursor += delta_paso

    return {
        "disponible": True,
        "fecha": fecha_str,
        "slots": slots_disponibles,
        "total_disponibles": len(slots_disponibles)
    }
