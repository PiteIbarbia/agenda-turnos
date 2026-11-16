// static/js/admin.js - Lógica interactiva para el Panel de Administración y Sincronización con Apple Calendar

document.addEventListener("DOMContentLoaded", () => {
  let authToken = sessionStorage.getItem("agenda_admin_token") || "";
  let allTurnos = [];
  let currentFilter = "proximos";

  // Vistas
  const loginView = document.getElementById("adminLoginView");
  const dashboardView = document.getElementById("adminDashboardView");
  const loginForm = document.getElementById("adminLoginForm");
  const loginPass = document.getElementById("adminPasswordInput");
  const loginAlert = document.getElementById("loginAlert");
  const logoutBtn = document.getElementById("btnLogout");

  // Pestañas
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Tabla y Filtros
  const turnosTableBody = document.getElementById("turnosTableBody");
  const searchInput = document.getElementById("searchTurnosInput");
  const filterPills = document.querySelectorAll(".filter-pill");

  // Apple Calendar Elementos
  const webcalUrlInput = document.getElementById("webcalUrlText");
  const btnCopyWebcal = document.getElementById("btnCopyWebcal");
  const btnOpenAppleDirect = document.getElementById("btnOpenAppleDirect");

  // Formulario de Configuración
  const configForm = document.getElementById("configForm");
  const configAlert = document.getElementById("configAlert");

  // 1. Verificación inicial de sesión
  if (authToken) {
    showDashboard();
  } else {
    showLogin();
  }

  function showLogin() {
    loginView.style.display = "block";
    dashboardView.style.display = "none";
    loginPass.focus();
  }

  function showDashboard() {
    loginView.style.display = "none";
    dashboardView.style.display = "block";
    loadDashboardData();
  }

  // 2. Login
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginAlert.style.display = "none";
    const password = loginPass.value.trim();

    try {
      const res = await fetch("/api/admin/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password })
      });
      const data = await res.json();
      if (!res.ok || data.error) {
        loginAlert.textContent = data.mensaje || "Contraseña incorrecta.";
        loginAlert.style.display = "block";
        return;
      }
      authToken = data.token;
      sessionStorage.setItem("agenda_admin_token", authToken);
      loginPass.value = "";
      showDashboard();
    } catch (err) {
      loginAlert.textContent = "Error al intentar iniciar sesión.";
      loginAlert.style.display = "block";
    }
  });

  // 3. Logout
  logoutBtn.addEventListener("click", () => {
    authToken = "";
    sessionStorage.removeItem("agenda_admin_token");
    showLogin();
  });

  // 4. Gestión de Pestañas
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(targetId).classList.add("active");
    });
  });

  // 5. Cargar Datos del Dashboard
  async function loadDashboardData() {
    await Promise.all([
      loadTurnos(),
      loadAdminConfig()
    ]);
  }

  // Cargar Turnos
  async function loadTurnos() {
    try {
      const res = await fetch("/api/admin/turnos", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (res.status === 401) {
        logoutBtn.click();
        return;
      }
      const data = await res.json();
      allTurnos = data.turnos || [];
      updateStats();
      renderTurnosTable();
    } catch (err) {
      console.error("Error al cargar turnos:", err);
    }
  }

  // Estadísticas
  function updateStats() {
    const todayStr = new Date().toISOString().slice(0, 10);
    const hoyCount = allTurnos.filter(t => t.fecha === todayStr && t.estado !== "cancelado").length;
    const proximosCount = allTurnos.filter(t => t.fecha >= todayStr && t.estado !== "cancelado").length;
    
    document.getElementById("statTotal").textContent = allTurnos.length;
    document.getElementById("statHoy").textContent = hoyCount;
    document.getElementById("statProximos").textContent = proximosCount;
  }

  // Filtros de tabla
  filterPills.forEach(pill => {
    pill.addEventListener("click", () => {
      filterPills.forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      currentFilter = pill.getAttribute("data-filter");
      renderTurnosTable();
    });
  });

  searchInput.addEventListener("input", () => {
    renderTurnosTable();
  });

  // Renderizar Tabla de Turnos
  function renderTurnosTable() {
    const todayStr = new Date().toISOString().slice(0, 10);
    const query = searchInput.value.toLowerCase().trim();

    const filtered = allTurnos.filter(t => {
      // Filtro de estado / fecha
      if (currentFilter === "hoy" && (t.fecha !== todayStr || t.estado === "cancelado")) return false;
      if (currentFilter === "proximos" && (t.fecha < todayStr || t.estado === "cancelado")) return false;
      if (currentFilter === "cancelados" && t.estado !== "cancelado") return false;
      if (currentFilter === "completados" && t.estado !== "completado") return false;

      // Filtro de búsqueda
      if (query) {
        const full = `${t.nombre} ${t.apellido} ${t.celular} ${t.motivo}`.toLowerCase();
        if (!full.includes(query)) return false;
      }
      return true;
    });

    turnosTableBody.innerHTML = "";

    if (filtered.length === 0) {
      turnosTableBody.innerHTML = `
        <tr>
          <td colspan="6" style="text-align: center; color: var(--gray-400); padding: 2rem;">
            No se encontraron turnos con el filtro seleccionado.
          </td>
        </tr>
      `;
      return;
    }

    filtered.forEach(t => {
      const tr = document.createElement("tr");

      // Celular limpio para enlace wa.me
      const cleanCelular = (t.celular || "").replace(/[^\d]/g, "");
      const waMsg = encodeURIComponent(
        `Hola ${t.nombre}, te contacto desde la agenda para coordinar tu turno del día ${t.fecha} a las ${t.hora_inicio} hs.`
      );
      const waUrl = `https://wa.me/${cleanCelular}?text=${waMsg}`;

      tr.innerHTML = `
        <td>
          <strong>${t.fecha}</strong><br>
          <span style="color: var(--gray-500); font-size: 0.825rem;">${t.hora_inicio} a ${t.hora_fin}</span>
        </td>
        <td class="client-name-cell">
          <strong>${escapeHtml(t.nombre)} ${escapeHtml(t.apellido)}</strong>
          <span>${escapeHtml(t.motivo || "Sin observaciones")}</span>
        </td>
        <td>
          <a href="tel:${t.celular}" style="color: var(--gray-800); text-decoration: none; font-weight: 500;">
            ${escapeHtml(t.celular)}
          </a>
        </td>
        <td>
          <span class="badge-status ${t.estado}">${t.estado}</span>
        </td>
        <td>
          <div class="actions-cell">
            <a href="${waUrl}" target="_blank" class="btn-action-wa" title="Escribir por WhatsApp">
              💬 WhatsApp
            </a>
            ${t.estado !== "cancelado" ? `
              <button class="btn-action-cancel" data-id="${t.id}" data-action="cancelar" title="Cancelar Turno">
                ❌
              </button>
            ` : ""}
            <button class="btn-action-cancel" data-id="${t.id}" data-action="eliminar" title="Eliminar definitivamente" style="color: #64748b; border-color: var(--gray-300);">
              🗑️
            </button>
          </div>
        </td>
      `;

      turnosTableBody.appendChild(tr);
    });

    // Asignar listeners a botones de acción
    turnosTableBody.querySelectorAll("button[data-action]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const action = btn.getAttribute("data-action");

        if (action === "cancelar") {
          if (!confirm("¿Deseas cancelar este turno? Se liberará el horario.")) return;
          await updateTurnoStatus(id, "cancelado");
        } else if (action === "eliminar") {
          if (!confirm("¿Estás seguro de eliminar permanentemente este registro?")) return;
          await deleteTurno(id);
        }
      });
    });
  }

  async function updateTurnoStatus(id, estado) {
    try {
      const res = await fetch("/api/admin/turnos/status", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({ id, estado })
      });
      if (res.ok) {
        await loadTurnos();
      }
    } catch (err) {
      alert("Error al actualizar turno");
    }
  }

  async function deleteTurno(id) {
    try {
      const res = await fetch("/api/admin/turnos/delete", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify({ id })
      });
      if (res.ok) {
        await loadTurnos();
      }
    } catch (err) {
      alert("Error al eliminar turno");
    }
  }

  // 6. Cargar y Configurar Sincronización con Apple Calendar
  async function loadAdminConfig() {
    try {
      const res = await fetch("/api/admin/config", {
        headers: { "Authorization": `Bearer ${authToken}` }
      });
      if (!res.ok) return;
      const cfg = await res.json();

      // Configurar URLs de Apple Calendar
      const webcalUrl = cfg.apple_calendar_webcal_url || "";
      webcalUrlInput.value = webcalUrl;
      btnOpenAppleDirect.href = webcalUrl;

      // Llenar formulario de ajustes
      document.getElementById("cfgTitulo").value = cfg.titulo_agenda || "";
      document.getElementById("cfgDescripcion").value = cfg.descripcion_agenda || "";
      document.getElementById("cfgProfesional").value = cfg.nombre_profesional || "";
      document.getElementById("cfgTelefono").value = cfg.telefono_contacto || "";
      document.getElementById("cfgDuracion").value = cfg.duracion_minutos || "45";
      document.getElementById("cfgBuffer").value = cfg.buffer_minutos || "15";
      document.getElementById("cfgApertura").value = cfg.hora_apertura || "09:00";
      document.getElementById("cfgCierre").value = cfg.hora_cierre || "18:00";
      document.getElementById("cfgPausaIni").value = cfg.pausa_inicio || "13:00";
      document.getElementById("cfgPausaFin").value = cfg.pausa_fin || "14:00";
      document.getElementById("cfgMaxDias").value = cfg.dias_anticipacion_max || "30";

      // Checkboxes de días laborales
      const dias = cfg.dias_laborales || [1, 2, 3, 4, 5];
      for (let i = 0; i <= 6; i++) {
        const chk = document.getElementById(`dayChk_${i}`);
        if (chk) chk.checked = dias.includes(i);
      }
    } catch (err) {
      console.error("Error al cargar configuración de admin:", err);
    }
  }

  // Copiar URL WebCal al portapapeles
  btnCopyWebcal.addEventListener("click", () => {
    webcalUrlInput.select();
    navigator.clipboard.writeText(webcalUrlInput.value).then(() => {
      btnCopyWebcal.textContent = "✅ ¡Copiado!";
      setTimeout(() => {
        btnCopyWebcal.textContent = "📋 Copiar Enlace";
      }, 2000);
    });
  });

  // Guardar Configuración
  configForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    configAlert.style.display = "none";

    const diasSeleccionados = [];
    for (let i = 0; i <= 6; i++) {
      const chk = document.getElementById(`dayChk_${i}`);
      if (chk && chk.checked) diasSeleccionados.push(i);
    }

    const payload = {
      titulo_agenda: document.getElementById("cfgTitulo").value.trim(),
      descripcion_agenda: document.getElementById("cfgDescripcion").value.trim(),
      nombre_profesional: document.getElementById("cfgProfesional").value.trim(),
      telefono_contacto: document.getElementById("cfgTelefono").value.trim(),
      duracion_minutos: parseInt(document.getElementById("cfgDuracion").value) || 45,
      buffer_minutos: parseInt(document.getElementById("cfgBuffer").value) || 15,
      hora_apertura: document.getElementById("cfgApertura").value,
      hora_cierre: document.getElementById("cfgCierre").value,
      pausa_inicio: document.getElementById("cfgPausaIni").value,
      pausa_fin: document.getElementById("cfgPausaFin").value,
      dias_anticipacion_max: parseInt(document.getElementById("cfgMaxDias").value) || 30,
      dias_laborales: diasSeleccionados
    };

    const newPass = document.getElementById("cfgNewPassword").value.trim();
    if (newPass) {
      payload.new_password = newPass;
    }

    try {
      const res = await fetch("/api/admin/config", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${authToken}`
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        configAlert.className = "alert alert-success";
        configAlert.textContent = "Configuración guardada correctamente.";
        configAlert.style.display = "block";
        document.getElementById("cfgNewPassword").value = "";
      } else {
        configAlert.className = "alert alert-danger";
        configAlert.textContent = data.mensaje || "Error al guardar configuración.";
        configAlert.style.display = "block";
      }
    } catch (err) {
      configAlert.className = "alert alert-danger";
      configAlert.textContent = "Error al conectar con el servidor.";
      configAlert.style.display = "block";
    }
  });

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }
});
