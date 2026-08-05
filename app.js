// desk-dashboard display client.
//
// Connects to the shell (GET /components for self-description, WS /stream for the
// merged envelopes) and renders whatever components currently exist — it has ZERO
// hardcoded component knowledge, so adding/removing a component on the cluster
// changes this display with no edit here. The shell URL comes from ?shell= ,
// persisted to localStorage; default is localhost for dev.

const params = new URLSearchParams(location.search);
const SHELL = (params.get("shell") || localStorage.getItem("shell") || "http://localhost:30080").replace(/\/$/, "");
const WS_URL = SHELL.replace(/^http/, "ws") + "/stream";
localStorage.setItem("shell", SHELL);

document.getElementById("shell-url").textContent = SHELL;
document.getElementById("cfg").onclick = () => {
  const v = prompt("Shell base URL (e.g. http://192.168.1.10:30080)", SHELL);
  if (v) location.search = "?shell=" + encodeURIComponent(v.replace(/\/$/, ""));
};

const grid = document.getElementById("grid");
const conn = document.getElementById("conn");
let manifests = {};   // id -> manifest (display_name, category, …)
let cards = {};       // id -> card element

async function loadComponents() {
  try {
    const r = await fetch(SHELL + "/components");
    const data = await r.json();
    manifests = Object.fromEntries((data.components || []).map((m) => [m.id, m]));
    pruneRemoved(data.components.map((m) => m.id));
  } catch (e) {
    setConn("discovery failed", "degraded");
  }
}

function connect() {
  setConn("connecting…", "disconnected");
  let ws;
  try {
    ws = new WebSocket(WS_URL);
  } catch (e) {
    setConn("bad URL", "disconnected");
    setTimeout(connect, 2000);
    return;
  }
  ws.onopen = () => loadComponents().then(() => setConn("live", "live"));
  ws.onmessage = (ev) => {
    const snap = JSON.parse(ev.data);
    document.getElementById("generated").textContent = "updated " + relTime(snap.generated_at);
    const ids = Object.keys(snap.components);
    document.getElementById("count").textContent = ids.length + " component" + (ids.length === 1 ? "" : "s");
    // A new component id we've never seen -> refresh /components so we can render its title/schema.
    if (ids.some((id) => !manifests[id])) loadComponents();
    for (const [id, env] of Object.entries(snap.components)) renderEnvelope(id, env);
    markStale(ids);
  };
  ws.onclose = () => { setConn("disconnected — retrying", "disconnected"); setTimeout(connect, 2000); };
  ws.onerror = () => ws.close();
}

// ── rendering ────────────────────────────────────────────────────────────────
function cardFor(id) {
  if (cards[id]) return cards[id];
  const m = manifests[id] || { id, display_name: id, category: "" };
  const card = document.createElement("section");
  card.className = "card";
  card.innerHTML = `<h2><span>${escapeHtml(m.display_name)}</span><span class="cat">${escapeHtml(m.category || "")}</span></h2>
                    <div class="ts"></div><div class="body"></div>`;
  card.dataset.status = "unreachable";
  grid.appendChild(card);
  cards[id] = card;
  return card;
}

function renderEnvelope(id, env) {
  const card = cardFor(id);
  card.dataset.status = env.status;
  card.querySelector(".ts").textContent = env.timestamp ? relTime(env.timestamp) : "";
  renderData(card.querySelector(".body"), env.data);
}

function renderData(el, data, keyPrefix = "") {
  el.innerHTML = "";
  if (data == null) { el.innerHTML = '<span class="nodata">no data</span>'; return; }
  if (Array.isArray(data)) { renderList(el, data); return; }
  if (typeof data === "object") {
    for (const [k, v] of Object.entries(data)) {
      if (v != null && typeof v === "object") {
        const sec = document.createElement("div");
        sec.className = "section";
        sec.innerHTML = `<div class="label">${escapeHtml(pretty(k))}</div>`;
        const inner = document.createElement("div");
        renderData(inner, v, k + ".");
        sec.appendChild(inner);
        el.appendChild(sec);
      } else {
        const row = document.createElement("div");
        row.className = "row";
        row.innerHTML = `<span class="k">${escapeHtml(pretty(k))}</span><span class="v">${escapeHtml(format(kPrefix + k, v))}</span>`;
        el.appendChild(row);
      }
    }
    if (!el.children.length) el.innerHTML = '<span class="nodata">empty</span>';
    return;
  }
  el.innerHTML = `<span class="v">${escapeHtml(format("", data))}</span>`;
}

function renderList(el, items) {
  if (!items.length) { el.innerHTML = '<span class="nodata">—</span>'; return; }
  if (items.every((i) => typeof i !== "object" || i === null)) {
    el.innerHTML = `<span class="v">${escapeHtml(items.map(format.bind(null, "")).join(", "))}</span>`;
    return;
  }
  for (const item of items) {
    const sub = document.createElement("div");
    sub.className = "sub";
    const label = item && (item.name || item.device || item.mount || item.summary || item.uid);
    if (label) sub.innerHTML = `<div class="sublabel">${escapeHtml(String(label))}</div>`;
    const inner = document.createElement("div");
    renderData(inner, omit(item, ["name", "device", "mount", "summary", "uid"]));
    sub.appendChild(inner);
    el.appendChild(sub);
  }
}

// ── formatting helpers ───────────────────────────────────────────────────────
const UNITS = [
  [/percent|usage$/i, (v) => v + "%"],
  [/celsius|temp/i, (v) => v + "°C"],
  [/_gib$/i, (v) => v + " GiB"],
  [/_mib$/i, (v) => (v >= 1024 ? (v / 1024).toFixed(1) + " GiB" : v + " MiB")],
  [/_mhz$/i, (v) => v + " MHz"],
  [/kmh|wind_speed/i, (v) => v + " km/h"],
  [/_per_sec$/i, (v) => rate(v)],
  [/humidity/i, (v) => v + "%"],
];

function format(key, v) {
  if (v == null) return "—";
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") {
    for (const [re, fmt] of UNITS) if (re.test(key)) return fmt(Number.isInteger(v) ? v : round(v));
    return String(round(v));
  }
  if (typeof v === "string" && /^\d{4}-\d\d-\d\dT/.test(v)) return new Date(v).toLocaleString();
  return String(v);
}

function rate(bytesPerSec) {
  const u = ["B/s", "KB/s", "MB/s", "GB/s"];
  let i = 0, v = bytesPerSec;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return (i === 0 ? v : v.toFixed(1)) + " " + u[i];
}

function round(v) { return Math.round(v * 100) / 100; }
function pretty(k) { return k.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase()); }
function omit(obj, keys) {
  if (!obj || typeof obj !== "object") return obj;
  const o = { ...obj };
  for (const k of keys) delete o[k];
  return o;
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function relTime(iso) { return new Date(iso).toLocaleTimeString(); }

// ── status / lifecycle ───────────────────────────────────────────────────────
function setConn(text, cls) { conn.textContent = text; conn.className = cls; }
function markStale(activeIds) {
  // dim cards that didn't appear in this frame (component removed/unreachable-and-dropped)
  for (const [id, card] of Object.entries(cards)) {
    if (!activeIds.includes(id)) card.dataset.status = "unreachable";
  }
}
function pruneRemoved(knownIds) {
  for (const id of Object.entries(cards).map(([id]) => id)) {
    if (!knownIds.includes(id)) { cards[id].remove(); delete cards[id]; }
  }
}

// re-fetch /components periodically so layout tracks add/remove even between frames
setInterval(loadComponents, 30000);
loadComponents();
connect();
