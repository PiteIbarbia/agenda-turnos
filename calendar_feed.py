"""
calendar_feed.py - Generador de archivos y feeds RFC 5545 iCalendar (.ics)
Compatible con Apple Calendar (iPhone, iPad, Mac), Google Calendar y Outlook.
"""

from datetime import datetime
import re

def escape_ical_text(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = text.replace("\\", "\\\\")
    text = text.replace(";", "\\;")
    text = text.replace(",", "\\,")
    text = text.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return text

def clean_phone_for_whatsapp(phone: str) -> str:
    """Elimina caracteres no numéricos para generar el enlace wa.me."""
    digits = re.sub(r"[^\d]", "", phone)
    return digits

def generate_ical_feed(turnos: list, calendar_name="Agenda de Turnos") -> str:
    """
    Genera el feed iCalendar completo para suscripción en Apple Calendar (WebCal).
    """
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Agenda Turnos//Sincronizacion Apple Calendar//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ical_text(calendar_name)}",
        "X-WR-CALDESC:Sincronización automática de turnos reservados",
        "REFRESH-INTERVAL;VALUE=DURATION:PT15M",
        "X-PUBLISHED-TTL:PT15M",
    ]

    for t in turnos:
        # Solo incluir turnos no cancelados en el calendario principal
        if t.get("estado") == "cancelado":
            continue

        fecha_str = t["fecha"].replace("-", "") # YYYYMMDD
        hora_inicio_str = t["hora_inicio"].replace(":", "") + "00" # HHMM00
        hora_fin_str = t["hora_fin"].replace(":", "") + "00" # HHMM00
        
        dtstart = f"{fecha_str}T{hora_inicio_str}"
        dtend = f"{fecha_str}T{hora_fin_str}"
        
        nombre_completo = f"{t['nombre']} {t['apellido']}".strip()
        celular = t.get('celular', '').strip()
        wa_digits = clean_phone_for_whatsapp(celular)
        wa_link = f"https://wa.me/{wa_digits}" if wa_digits else ""
        motivo = t.get('motivo', '').strip()
        
        desc_parts = [
            f"👤 Cliente: {nombre_completo}",
            f"📱 Teléfono / WhatsApp: {celular}",
        ]
        if wa_link:
            desc_parts.append(f"💬 Chatear por WhatsApp: {wa_link}")
        if motivo:
            desc_parts.append(f"📝 Motivo/Consulta: {motivo}")
        desc_parts.append("✅ Turno agendado desde la web")
        
        description = "\\n".join(escape_ical_text(p) for p in desc_parts)
        summary = escape_ical_text(f"Turno: {nombre_completo}")

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:turno-{t['id']}@agendaturnos.local",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{escape_ical_text(celular)}",
            "STATUS:CONFIRMED",
            "TRANSP:OPAQUE",
        ])

        if wa_link:
            lines.append(f"URL;VALUE=URI:{wa_link}")

        # Alarma / Notificación de Apple Calendar 30 minutos antes
        lines.extend([
            "BEGIN:VALARM",
            "TRIGGER:-PT30M",
            "ACTION:DISPLAY",
            f"DESCRIPTION:Turno próximo con {escape_ical_text(nombre_completo)}",
            "END:VALARM",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

def generate_single_event_ics(turno: dict, business_name="Agenda") -> str:
    """
    Genera un archivo .ics individual para que el cliente lo descargue
    y lo agregue a su propio calendario (Apple, Google, etc.).
    """
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fecha_str = turno["fecha"].replace("-", "")
    hora_inicio_str = turno["hora_inicio"].replace(":", "") + "00"
    hora_fin_str = turno["hora_fin"].replace(":", "") + "00"

    dtstart = f"{fecha_str}T{hora_inicio_str}"
    dtend = f"{fecha_str}T{hora_fin_str}"

    summary = escape_ical_text(f"Cita con {business_name}")
    description = escape_ical_text(
        f"Tu turno ha sido confirmado con {business_name}.\\n"
        f"Fecha: {turno['fecha']}\\n"
        f"Horario: {turno['hora_inicio']} a {turno['hora_fin']}"
    )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Agenda Turnos//Cliente//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:turno-cliente-{turno['id']}@agendaturnos.local",
        f"DTSTAMP:{now_utc}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        "STATUS:CONFIRMED",
        "BEGIN:VALARM",
        "TRIGGER:-PT60M",
        "ACTION:DISPLAY",
        f"DESCRIPTION:Recordatorio: {summary}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR"
    ]
    return "\r\n".join(lines) + "\r\n"
