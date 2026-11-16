# 📅 Agenda de Turnos Online & Sincronización con Apple Calendar

Sistema web ligero, moderno y autónomo para reserva de citas y turnos de clientes con panel de administración y sincronización automática en tiempo real con **Apple Calendar (iPhone, iPad, Mac)** mediante el estándar iCalendar (WebCal RFC 5545).

---

## 🚀 Inicio Rápido (En 1 Segundo)

No requiere instalar librerías pesadas ni dependencias externas; funciona con la librería estándar de **Python 3**.

### En Windows:
1. Haz **doble clic en `run.bat`** (o ejecuta `python server.py`).
2. Se abrirá la consola indicando las direcciones locales y de tu red Wi-Fi:
   * **Web pública para clientes:** `http://localhost:5000`
   * **Panel de administración:** `http://localhost:5000/admin` (Contraseña inicial: `admin`)

---

## 🌟 Características Principales

### 1. Para tus Clientes (`/`)
* **Campos obligatorios:**
  * **Nombre**
  * **Apellido**
  * **Celular / WhatsApp**
  * Motivo o consulta (opcional)
* **Reserva en 1 Clic:** Selección visual e interactiva de fecha y horario disponible.
* **Confirmación Inmediata:**
  * 💬 Botón directo para avisar al administrador por WhatsApp con un mensaje preconfigurado.
  * 🍏 Botón para añadir la cita a su propio calendario (Apple, Google o Outlook).

### 2. Para ti como Administrador (`/admin`)
* **Gestión de Turnos:**
  * Filtros rápidos: *Próximos*, *Hoy*, *Todos*, *Completados*, *Cancelados*.
  * Buscador en tiempo real por nombre, apellido o teléfono.
  * 💬 **Botón directo de WhatsApp:** Inicia una conversación con el cliente con un mensaje prearmado: *"Hola [Nombre], te contacto desde la agenda para coordinar tu turno del día [Fecha] a las [Hora]"*.
  * Cancelar turnos (libera el horario automáticamente en la web).
* **Configuración de Horarios:**
  * Días laborales habilitados (Lunes a Domingo).
  * Horarios de apertura y cierre.
  * Pausa de almuerzo/descanso.
  * Duración de cada turno (15, 30, 45, 60, 90 o 120 minutos).
  * Tiempo de descanso entre turnos (buffer de 5, 10, 15 min).
  * Días de anticipación máxima.
  * Cambio de clave de acceso.

---

## 🍏 Sincronización con Apple Calendar

Cada vez que un cliente reserva un turno, este aparece automáticamente en la app **Calendario** de tu iPhone, iPad y Mac.

### ¿Cómo configurarlo en tu iPhone o iPad?
1. Entra a tu panel de administración en Safari desde tu iPhone (ej: `http://TU_IP_LOCAL:5000/admin`).
2. En la tarjeta superior de **Apple Calendar**, toca el botón **"Suscribirme en Apple Calendar (1 Clic)"**.
3. Tu iPhone te preguntará si deseas suscribirte al calendario. Toca **Suscribirse** y luego **Guardar**.
4. *(Método manual)*: En tu iPhone ve a **Ajustes > Calendario > Cuentas > Añadir cuenta > Otra > Añadir suscripción a calendario** y pega la URL que te da el panel (`webcal://...`).

### ¿Cómo configurarlo en tu Mac (macOS)?
1. Abre la app **Calendario** en tu Mac.
2. En la barra de menú superior ve a **Archivo > Nueva suscripción de calendario...** (o pulsa `Option + Command + S`).
3. Pega la URL del feed del panel de administración.
4. En el campo **Frecuencia de actualización**, selecciona **Cada 15 minutos** y haz clic en Aceptar.

**¡Listo!** En cada evento de Apple Calendar verás:
* Nombre y Apellido del cliente.
* Número de WhatsApp con enlace directo para chatear.
* Motivo de la consulta.
* Alarma/notificación automática 30 minutos antes.

---

## 🌐 ¿Cómo compartir el link con clientes por Internet?

Si deseas que personas fuera de tu red Wi-Fi local puedan agendar:
1. **Opción Rápida con Cloudflare Tunnel (Gratis y sin abrir puertos):**
   ```bash
   cloudflared tunnel --url http://localhost:5000
   ```
   Te dará un enlace público seguro `https://tu-agenda.trycloudflare.com` que puedes poner en tu perfil de Instagram o enviar por WhatsApp.
2. **Despliegue en la nube (Gratis 24/7):**
   Puedes subir esta misma carpeta a servicios como **Render**, **Railway** o **PythonAnywhere** ejecutando `python server.py`.

---

## 📁 Estructura del Proyecto

```
agenda_turnos/
├── server.py              # Servidor HTTP multihilo y rutas API
├── database.py            # Base de datos SQLite (turnos y configuración)
├── slot_calculator.py     # Algoritmo de cálculo de horarios disponibles
├── calendar_feed.py       # Generador de feeds RFC 5545 iCalendar (.ics)
├── test_server.py         # Suite de pruebas automáticas
├── run.bat                # Ejecutable rápido para Windows
├── run.ps1                # Script para PowerShell
├── static/
│   ├── index.html         # Página de reserva para clientes
│   ├── admin.html         # Panel de control del administrador
│   ├── css/
│   │   └── style.css      # Diseño visual moderno y responsivo
│   └── js/
│       ├── app.js         # Lógica interactiva del cliente
│       └── admin.js       # Lógica del panel de administración
└── agenda.db              # Base de datos SQLite generada automáticamente
```
