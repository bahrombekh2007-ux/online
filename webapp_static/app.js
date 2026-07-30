const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor("#12151C");
  tg.setBackgroundColor("#12151C");
}

const STATUS_LABELS = { faol: "onlayn", pauza: "pauzada", xatolik: "xatolik" };

const PULSE_PATHS = {
  faol: "M0,16 L10,16 L15,4 L20,28 L25,16 L36,16 L41,8 L46,16 L56,16",
  pauza: "M0,16 L56,16",
  xatolik: "M0,16 L56,16",
};

let currentAccounts = [];
let activeDetailId = null;

function pulseSVG(status) {
  const d = PULSE_PATHS[status] || PULSE_PATHS.pauza;
  return `<svg viewBox="0 0 56 32"><path class="pulse-line status-${status}" d="${d}"/></svg>`;
}

function timeAgo(isoString) {
  if (!isoString) return "hali yo'q";
  const diffMs = Date.now() - new Date(isoString + "Z").getTime();
  const sec = Math.floor(diffMs / 1000);
  if (sec < 60) return `${sec} soniya oldin`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} daqiqa oldin`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} soat oldin`;
  return `${Math.floor(hr / 24)} kun oldin`;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Telegram-Init-Data": tg?.initData || "",
      ...(options.headers || {}),
    },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Xatolik yuz berdi");
  return data;
}

function renderAccounts(accounts) {
  currentAccounts = accounts;
  const list = document.getElementById("accountsList");
  const empty = document.getElementById("emptyState");

  if (!accounts.length) {
    list.innerHTML = "";
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  list.innerHTML = accounts.map((acc, i) => {
    const tags = [];
    if (acc.schedule_enabled) {
      tags.push(`<span class="tag on">🌙 ${acc.online_start_hour}:00–${acc.online_end_hour}:00</span>`);
    } else {
      tags.push(`<span class="tag">🌙 doim onlayn</span>`);
    }
    if (acc.auto_read) tags.push(`<span class="tag on">👁 auto-read</span>`);

    return `
      <div class="account-card" data-id="${acc.id}" style="animation-delay:${i * 40}ms">
        <div class="account-pulse">${pulseSVG(acc.status)}</div>
        <div class="account-info">
          <div class="account-name">${escapeHtml(acc.name || acc.phone)}</div>
          <div class="account-phone">${escapeHtml(acc.phone)}</div>
          <div class="account-meta">${tags.join("")}</div>
        </div>
        <div class="account-status">
          <span class="status-badge status-${acc.status}">${STATUS_LABELS[acc.status] || acc.status}</span>
          <div class="account-last">${timeAgo(acc.last_online)}</div>
        </div>
      </div>`;
  }).join("");

  list.querySelectorAll(".account-card").forEach(card => {
    card.addEventListener("click", () => openDetail(Number(card.dataset.id)));
  });
}

function renderStats(stats) {
  document.getElementById("statTotal").textContent = stats.total;
  document.getElementById("statOnline").textContent = stats.online;
  document.getElementById("statPaused").textContent = stats.paused;
  document.getElementById("statError").textContent = stats.error;
}

async function loadData() {
  try {
    const data = await api("/api/accounts");
    renderStats(data.stats);
    renderAccounts(data.accounts);
    document.getElementById("errorState").hidden = true;
    document.getElementById("lastUpdated").textContent =
      "yangilandi: " + new Date().toLocaleTimeString("uz-UZ");
    if (activeDetailId) refreshDetailView();
  } catch (e) {
    document.getElementById("errorState").hidden = false;
    document.getElementById("errorHint").textContent = e.message;
  }
}

const backdrop = document.getElementById("sheetBackdrop");
const sheetTitle = document.getElementById("sheetTitle");
const sheetError = document.getElementById("sheetError");
const allSteps = ["stepPhone", "stepCode", "stepPassword", "stepName", "stepSuccess", "stepDetail"];

function showStep(id) {
  allSteps.forEach(s => document.getElementById(s).hidden = (s !== id));
  sheetError.hidden = true;
}

function openSheet(title) {
  sheetTitle.textContent = title;
  backdrop.hidden = false;
}

function closeSheet() {
  backdrop.hidden = true;
  activeDetailId = null;
}

document.getElementById("sheetClose").addEventListener("click", closeSheet);
backdrop.addEventListener("click", (e) => { if (e.target === backdrop) closeSheet(); });

function showError(msg) {
  sheetError.textContent = msg;
  sheetError.hidden = false;
}

document.getElementById("fabAdd").addEventListener("click", () => {
  document.getElementById("inputPhone").value = "";
  document.getElementById("inputCode").value = "";
  document.getElementById("inputPassword").value = "";
  document.getElementById("inputName").value = "";
  showStep("stepPhone");
  openSheet("Akkaunt qo'shish");
});

document.getElementById("btnSendPhone").addEventListener("click", async () => {
  const phone = document.getElementById("inputPhone").value.trim();
  const btn = document.getElementById("btnSendPhone");
  btn.disabled = true;
  try {
    await api("/api/add/request-code", { method: "POST", body: JSON.stringify({ phone }) });
    showStep("stepCode");
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("btnSendCode").addEventListener("click", async () => {
  const code = document.getElementById("inputCode").value.trim();
  const btn = document.getElementById("btnSendCode");
  btn.disabled = true;
  try {
    const res = await api("/api/add/verify-code", { method: "POST", body: JSON.stringify({ code }) });
    showStep(res.step === "password" ? "stepPassword" : "stepName");
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("btnSendPassword").addEventListener("click", async () => {
  const password = document.getElementById("inputPassword").value;
  const btn = document.getElementById("btnSendPassword");
  btn.disabled = true;
  try {
    await api("/api/add/verify-password", { method: "POST", body: JSON.stringify({ password }) });
    showStep("stepName");
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("btnFinish").addEventListener("click", async () => {
  const name = document.getElementById("inputName").value.trim();
  const btn = document.getElementById("btnFinish");
  btn.disabled = true;
  try {
    await api("/api/add/finish", { method: "POST", body: JSON.stringify({ name }) });
    showStep("stepSuccess");
    loadData();
  } catch (e) {
    showError(e.message);
  } finally {
    btn.disabled = false;
  }
});

document.getElementById("btnDone").addEventListener("click", closeSheet);

function findAccount(id) {
  return currentAccounts.find(a => a.id === id);
}

function fillDetailView(acc) {
  document.getElementById("detailPulse").innerHTML = pulseSVG(acc.status);
  document.getElementById("detailName").textContent = acc.name || acc.phone;
  document.getElementById("detailPhone").textContent = acc.phone;

  const badge = document.getElementById("detailStatusBadge");
  badge.textContent = STATUS_LABELS[acc.status] || acc.status;
  badge.className = "status-badge status-" + acc.status;

  document.getElementById("detailLastOnline").textContent = timeAgo(acc.last_online);

  const toggleBtn = document.getElementById("btnToggleStatus");
  toggleBtn.textContent = acc.status === "faol" ? "⏸ Pauza qilish" : "▶️ Davom ettirish";

  document.getElementById("toggleSchedule").checked = !!acc.schedule_enabled;
  document.getElementById("scheduleHours").hidden = !acc.schedule_enabled;
  document.getElementById("scheduleStart").value = acc.online_start_hour;
  document.getElementById("scheduleEnd").value = acc.online_end_hour;

  document.getElementById("toggleAutoread").checked = !!acc.auto_read;
}

function refreshDetailView() {
  const acc = findAccount(activeDetailId);
  if (acc) fillDetailView(acc);
}

function openDetail(id) {
  const acc = findAccount(id);
  if (!acc) return;
  activeDetailId = id;
  fillDetailView(acc);
  showStep("stepDetail");
  openSheet("Akkaunt");
}

document.getElementById("btnToggleStatus").addEventListener("click", async () => {
  const acc = findAccount(activeDetailId);
  if (!acc) return;
  const action = acc.status === "faol" ? "pause" : "resume";
  try {
    await api(`/api/accounts/${activeDetailId}/${action}`, { method: "POST" });
    await loadData();
  } catch (e) {
    showError(e.message);
  }
});

document.getElementById("toggleSchedule").addEventListener("change", async (e) => {
  const enabled = e.target.checked;
  document.getElementById("scheduleHours").hidden = !enabled;
  const start = Number(document.getElementById("scheduleStart").value) || 8;
  const end = Number(document.getElementById("scheduleEnd").value) || 24;
  try {
    await api(`/api/accounts/${activeDetailId}/schedule`, {
      method: "POST",
      body: JSON.stringify({ enabled, start_hour: start, end_hour: end }),
    });
    await loadData();
  } catch (err) {
    showError(err.message);
  }
});

["scheduleStart", "scheduleEnd"].forEach(id => {
  document.getElementById(id).addEventListener("change", async () => {
    const start = Number(document.getElementById("scheduleStart").value) || 8;
    const end = Number(document.getElementById("scheduleEnd").value) || 24;
    try {
      await api(`/api/accounts/${activeDetailId}/schedule`, {
        method: "POST",
        body: JSON.stringify({ enabled: true, start_hour: start, end_hour: end }),
      });
      await loadData();
    } catch (err) {
      showError(err.message);
    }
  });
});

document.getElementById("toggleAutoread").addEventListener("change", async (e) => {
  try {
    await api(`/api/accounts/${activeDetailId}/autoread`, {
      method: "POST",
      body: JSON.stringify({ enabled: e.target.checked }),
    });
    await loadData();
  } catch (err) {
    showError(err.message);
  }
});

document.getElementById("btnDeleteAccount").addEventListener("click", async () => {
  const acc = findAccount(activeDetailId);
  if (!acc) return;
  const ok = window.confirm(`"${acc.name || acc.phone}" akkauntini o'chirmoqchimisiz? Bu amalni orqaga qaytarib bo'lmaydi.`);
  if (!ok) return;
  try {
    await api(`/api/accounts/${activeDetailId}/delete`, { method: "POST" });
    closeSheet();
    await loadData();
  } catch (e) {
    showError(e.message);
  }
});

loadData();
setInterval(loadData, 5000);
