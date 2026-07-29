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

function renderAccounts(accounts) {
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
      <div class="account-card" style="animation-delay:${i * 40}ms">
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
}

function renderStats(stats) {
  document.getElementById("statTotal").textContent = stats.total;
  document.getElementById("statOnline").textContent = stats.online;
  document.getElementById("statPaused").textContent = stats.paused;
  document.getElementById("statError").textContent = stats.error;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

async function loadData() {
  try {
    const res = await fetch("/api/accounts", {
      headers: { "X-Telegram-Init-Data": tg?.initData || "" },
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    renderStats(data.stats);
    renderAccounts(data.accounts);
    document.getElementById("errorState").hidden = true;
    document.getElementById("lastUpdated").textContent =
      "yangilandi: " + new Date().toLocaleTimeString("uz-UZ");
  } catch (e) {
    document.getElementById("errorState").hidden = false;
    document.getElementById("errorHint").textContent = e.message;
  }
}

loadData();
setInterval(loadData, 5000);
