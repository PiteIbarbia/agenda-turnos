// static/js/app.js - Lógica interactiva para la reserva de turnos del cliente

document.addEventListener("DOMContentLoaded", () => {
  // Estado local
  let currentConfig = null;
  let viewDate = new Date();
  let selectedDateStr = null;
  let selectedSlot = null;

  const MONTH_NAMES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
  ];
  const DAY_NAMES_SHORT = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];

  // Elementos del DOM
  const calTitle = document.getElementById("calMonthTitle");
  const calGrid = document.getElementById("calendarGrid");
  const prevMonthBtn = document.getElementById("prevMonthBtn");
  const nextMonthBtn = document.getElementById("nextMonthBtn");
  const slotsGrid = document.getElementById("slotsGrid");
  const slotsNotice = document.getElementById("slotsNotice");
  const selectedDateLabel = document.getElementById("selectedDateLabel");

  const bookingForm = document.getElementById("bookingForm");
  const slotBanner = document.getElementById("selectedSlotBanner");
  const bannerText = document.getElementById("bannerDateTimeText");
  const submitBtn = document.getElementById("submitBookingBtn");
  const formAlert = document.getElementById("formAlert");

  const bookingView = document.getElementById("bookingView");
  const successView = document.getElementById("successView");

  // 1. Cargar Configuración Pública
  async function loadConfig() {
    try {
      const res = await fetch("/api/config");
      currentConfig = await res.json();
      if (currentConfig.titulo_agenda) {
        document.getElementById("heroTitle").textContent = currentConfig.titulo_agenda;
        document.title = currentConfig.titulo_agenda;
      }
      if (currentConfig.descripcion_agenda) {
        document.getElementById("heroDesc").textContent = currentConfig.descripcion_agenda;
      }
      renderCalendar();
      // Seleccionar automáticamente el primer día hábil a partir de hoy
      autoSelectFirstAvailableDate();
    } catch (err) {
      console.error("Error al cargar configuración:", err);
    }
  }

  // 2. Renderizar Calendario
  function renderCalendar() {
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();

    calTitle.textContent = `${MONTH_NAMES[month]} ${year}`;
    calGrid.innerHTML = "";

    // Encabezados de días de la semana
    DAY_NAMES_SHORT.forEach(day => {
      const el = document.createElement("div");
      el.className = "calendar-day-header";
      el.textContent = day;
      calGrid.appendChild(el);
    });

    const firstDayIndex = new Date(year, month, 1).getDay(); // 0=Dom, 1=Lun...
    const daysInMonth = new Date(year, month + 1, 0).getDate();

    // Celdas vacías al inicio
    for (let i = 0; i < firstDayIndex; i++) {
      const emptyCell = document.createElement("div");
      emptyCell.className = "cal-day-cell empty";
      calGrid.appendChild(emptyCell);
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const maxDays = currentConfig?.dias_anticipacion_max || 30;
    const maxDate = new Date();
    maxDate.setDate(today.getDate() + maxDays);
    maxDate.setHours(23, 59, 59, 999);

    const diasLaborales = currentConfig?.dias_laborales || [1, 2, 3, 4, 5];

    for (let dayNum = 1; dayNum <= daysInMonth; dayNum++) {
      const cellDate = new Date(year, month, dayNum);
      cellDate.setHours(0, 0, 0, 0);

      const dayOfWeek = cellDate.getDay(); // 0=Dom, ..., 6=Sáb
      const isPast = cellDate < today;
      const isTooFar = cellDate > maxDate;
      const isWorkDay = diasLaborales.includes(dayOfWeek);

      const cell = document.createElement("div");
      cell.className = "cal-day-cell";
      cell.textContent = dayNum;

      const dateStr = formatDateString(cellDate);

      if (cellDate.getTime() === today.getTime()) {
        cell.classList.add("today");
      }

      if (isPast || isTooFar || !isWorkDay) {
        cell.classList.add("disabled");
      } else {
        cell.classList.add("available");
        if (selectedDateStr === dateStr) {
          cell.classList.add("selected");
        }
        cell.addEventListener("click", () => {
          selectDate(dateStr, cell);
        });
      }

      calGrid.appendChild(cell);
    }
  }

  // Navegación del calendario
  prevMonthBtn.addEventListener("click", () => {
    viewDate.setMonth(viewDate.getMonth() - 1);
    renderCalendar();
  });

  nextMonthBtn.addEventListener("click", () => {
    viewDate.setMonth(viewDate.getMonth() + 1);
    renderCalendar();
  });

  function formatDateString(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${y}-${m}-${day}`;
  }

  function autoSelectFirstAvailableDate() {
    const today = new Date();
    const diasLaborales = currentConfig?.dias_laborales || [1, 2, 3, 4, 5];
    for (let i = 0; i < 14; i++) {
      const check = new Date();
      check.setDate(today.getDate() + i);
      if (diasLaborales.includes(check.getDay())) {
        const dateStr = formatDateString(check);
        selectDate(dateStr);
        break;
      }
    }
  }

  // 3. Selección de Fecha
  async function selectDate(dateStr, cellEl = null) {
    selectedDateStr = dateStr;
    selectedSlot = null;
    updateSelectedBanner();
    renderCalendar();

    // Formatear texto amigable
    const parts = dateStr.split("-");
    const dateObj = new Date(parts[0], parts[1] - 1, parts[2]);
    const options = { weekday: "long", year: "numeric", month: "long", day: "numeric" };
    const readable = dateObj.toLocaleDateString("es-ES", options);
    selectedDateLabel.textContent = readable.charAt(0).toUpperCase() + readable.slice(1);

    // Cargar horarios disponibles desde la API
    slotsGrid.innerHTML = "";
    slotsNotice.style.display = "block";
    slotsNotice.textContent = "Buscando horarios disponibles...";

    try {
      const res = await fetch(`/api/slots?date=${dateStr}`);
      const data = await res.json();

      if (!data.disponible || !data.slots || data.slots.length === 0) {
        slotsNotice.style.display = "block";
        slotsNotice.textContent = data.mensaje || "No quedan horarios disponibles para este día. Por favor elige otra fecha.";
        return;
      }

      slotsNotice.style.display = "none";
      data.slots.forEach(slot => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "slot-btn";
        btn.textContent = slot.hora_inicio;
        btn.title = `Turno de ${slot.hora_inicio} a ${slot.hora_fin}`;

        btn.addEventListener("click", () => {
          document.querySelectorAll(".slot-btn").forEach(b => b.classList.remove("selected"));
          btn.classList.add("selected");
          selectedSlot = slot;
          updateSelectedBanner();
        });

        slotsGrid.appendChild(btn);
      });
    } catch (err) {
      slotsNotice.style.display = "block";
      slotsNotice.textContent = "Error al consultar horarios. Intenta nuevamente.";
    }
  }

  // 4. Actualizar Banner de Horario Seleccionado
  function updateSelectedBanner() {
    if (selectedDateStr && selectedSlot) {
      slotBanner.style.display = "flex";
      const parts = selectedDateStr.split("-");
      const d = new Date(parts[0], parts[1] - 1, parts[2]);
      const dateText = d.toLocaleDateString("es-ES", { weekday: "short", day: "numeric", month: "short" });
      bannerText.textContent = `${dateText} a las ${selectedSlot.hora_inicio} hs (${selectedSlot.hora_fin} fin)`;
      submitBtn.disabled = false;
    } else {
      slotBanner.style.display = "none";
      submitBtn.disabled = true;
    }
  }

  // 5. Envío del Formulario de Reserva
  bookingForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    formAlert.style.display = "none";

    const nombre = document.getElementById("clientNombre").value.trim();
    const apellido = document.getElementById("clientApellido").value.trim();
    const celular = document.getElementById("clientCelular").value.trim();
    const motivo = document.getElementById("clientMotivo").value.trim();

    if (!nombre || !apellido || !celular) {
      showAlert("Por favor completa los campos obligatorios: Nombre, Apellido y Celular.", "danger");
      return;
    }

    if (!selectedDateStr || !selectedSlot) {
      showAlert("Debes seleccionar una fecha y un horario para tu turno.", "danger");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span>Agendando...</span>`;

    try {
      const res = await fetch("/api/turnos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          nombre,
          apellido,
          celular,
          motivo,
          fecha: selectedDateStr,
          hora_inicio: selectedSlot.hora_inicio,
          hora_fin: selectedSlot.hora_fin
        })
      });

      const data = await res.json();

      if (!res.ok || data.error) {
        showAlert(data.mensaje || "Ocurrió un error al reservar el turno.", "danger");
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>Confirmar Turno en 1 Clic 📅</span>`;
        // Recargar horarios por si fue tomado
        selectDate(selectedDateStr);
        return;
      }

      // Éxito: Mostrar pantalla de confirmación
      showSuccessScreen(data.turno, data.ics_download_url);
    } catch (err) {
      showAlert("No se pudo conectar con el servidor. Revisa tu conexión.", "danger");
      submitBtn.disabled = false;
      submitBtn.innerHTML = `<span>Confirmar Turno en 1 Clic 📅</span>`;
    }
  });

  function showAlert(msg, type = "danger") {
    formAlert.className = `alert alert-${type}`;
    formAlert.textContent = msg;
    formAlert.style.display = "block";
  }

  // 6. Pantalla de Éxito y Opciones
  function showSuccessScreen(turno, icsUrl) {
    bookingView.style.display = "none";
    successView.style.display = "block";

    document.getElementById("successClientName").textContent = `${turno.nombre} ${turno.apellido}`;
    document.getElementById("successDateTime").textContent = `${turno.fecha} de ${turno.hora_inicio} a ${turno.hora_fin} hs`;
    document.getElementById("successPhone").textContent = turno.celular;

    // Configurar botón para descargar .ics a Apple Calendar / Google Calendar
    const btnIcs = document.getElementById("btnDownloadClientIcs");
    btnIcs.href = icsUrl;

    // Configurar botón para notificar al Administrador por WhatsApp
    const adminPhone = currentConfig?.telefono_contacto || "";
    const cleanAdminPhone = adminPhone.replace(/[^\d]/g, "");
    const btnWa = document.getElementById("btnNotifyWhatsApp");

    const mensajeWa = encodeURIComponent(
      `¡Hola! Acabo de reservar un turno a nombre de ${turno.nombre} ${turno.apellido} para el día ${turno.fecha} a las ${turno.hora_inicio} hs.`
    );

    if (cleanAdminPhone) {
      btnWa.href = `https://wa.me/${cleanAdminPhone}?text=${mensajeWa}`;
    } else {
      btnWa.href = `https://wa.me/?text=${mensajeWa}`;
    }

    // Botón para volver a agendar
    document.getElementById("btnBookAnother").addEventListener("click", () => {
      bookingForm.reset();
      selectedSlot = null;
      updateSelectedBanner();
      successView.style.display = "none";
      bookingView.style.display = "grid";
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Confirmar Turno en 1 Clic 📅</span>`;
      selectDate(selectedDateStr);
    });
  }

  // Inicializar
  loadConfig();
});
