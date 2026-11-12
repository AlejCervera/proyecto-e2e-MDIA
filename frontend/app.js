// Frontend: mapa de trenes en directo y alertas recientes.
// Consulta el backend FastAPI a través de nginx (/api → backend:8000).

const API = "/api";
const POLL_MS = 15000;          // cada cuánto se piden datos (igual que el colector)
const ANIM_MS = POLL_MS;        // la animación dura un ciclo: el tren se mueve de forma continua
const MAX_ANIM_JUMP_M = 20000;  // saltos mayores no se animan (dato anómalo): se "teletransporta"
const RECENT_ALERT_S = 90;      // alertas detectadas hace menos de esto se consideran activas

const COLORS = { moving: "#1d4ed8", stopped: "#9ca3af", alert: "#dc2626" };

// ---------------------------------------------------------------------------
// Mapa
// ---------------------------------------------------------------------------
const map = L.map("map", { preferCanvas: true }).setView([40.2, -3.7], 6);
L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

const alertLayer = L.layerGroup().addTo(map);

// vehicle_id -> { marker, from: [lat, lon], to: [lat, lon], start: ms, data }
const trains = new Map();

// ---------------------------------------------------------------------------
// Utilidades
// ---------------------------------------------------------------------------
async function getJSON(path) {
  const res = await fetch(API + path, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function fmtTime(iso) {
  return new Date(iso).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function metersBetween([lat1, lon1], [lat2, lon2]) {
  return map.distance([lat1, lon1], [lat2, lon2]);
}

function trainColor(t, inAlert) {
  if (inAlert) return COLORS.alert;
  return t.status === "STOPPED_AT" ? COLORS.stopped : COLORS.moving;
}

function tooltipHtml(t) {
  const status = t.status === "STOPPED_AT" ? "Parado" : t.status === "IN_TRANSIT_TO" ? "En marcha" : (t.status ?? "—");
  return `<b>Tren ${escapeHtml(t.vehicle_id)}</b><br>
    ${status}${t.stop_id ? ` · parada ${escapeHtml(t.stop_id)}` : ""}<br>
    ${t.latitude.toFixed(5)}, ${t.longitude.toFixed(5)}<br>
    <small>recibido hace ${Math.round(t.age_seconds)} s</small>`;
}

// ---------------------------------------------------------------------------
// Trenes: crear, mover y borrar marcadores
// ---------------------------------------------------------------------------
function updateTrains(list, alertIds) {
  const now = performance.now();
  const seen = new Set();

  for (const t of list) {
    seen.add(t.vehicle_id);
    const target = [t.latitude, t.longitude];
    const color = trainColor(t, alertIds.has(t.vehicle_id));
    let entry = trains.get(t.vehicle_id);

    if (!entry) {
      const marker = L.circleMarker(target, {
        radius: 6, weight: 1.5, color: "#fff", fillColor: color, fillOpacity: 0.95,
      }).addTo(map);
      entry = { marker, from: target, to: target, start: now };
      trains.set(t.vehicle_id, entry);
    } else {
      const current = entry.marker.getLatLng();
      const from = [current.lat, current.lng];
      const jump = metersBetween(from, target);
      // Si el salto es enorme, no tiene sentido animarlo: se coloca directamente
      entry.from = jump > MAX_ANIM_JUMP_M ? target : from;
      entry.to = target;
      entry.start = now;
      entry.marker.setStyle({ fillColor: color });
    }

    entry.data = t;
    entry.marker.setRadius(alertIds.has(t.vehicle_id) ? 8 : 6);
    entry.marker.bindTooltip(tooltipHtml(t));
  }

  // Trenes que ya no aparecen: se quitan del mapa
  for (const [id, entry] of trains) {
    if (!seen.has(id)) {
      map.removeLayer(entry.marker);
      trains.delete(id);
    }
  }
}

// Bucle de animación: interpola cada tren entre su posición anterior y la nueva
function animate(now) {
  for (const entry of trains.values()) {
    const k = Math.min(1, (now - entry.start) / ANIM_MS);
    if (k >= 1 && entry.from === entry.to) continue;
    const lat = entry.from[0] + (entry.to[0] - entry.from[0]) * k;
    const lon = entry.from[1] + (entry.to[1] - entry.from[1]) * k;
    entry.marker.setLatLng([lat, lon]);
    if (k >= 1) entry.from = entry.to;
  }
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

// ---------------------------------------------------------------------------
// Alertas: líneas en el mapa y lista en el panel
// ---------------------------------------------------------------------------
function activeAlerts(alerts) {
  // Solo las recientes, y una por par (la más nueva: vienen ordenadas desc)
  const byPair = new Map();
  for (const a of alerts) {
    const ageS = (Date.now() - Date.parse(a.detected_at)) / 1000;
    if (ageS > RECENT_ALERT_S) continue;
    const key = `${a.train_a}|${a.train_b}`;
    if (!byPair.has(key)) byPair.set(key, a);
  }
  return [...byPair.values()];
}

function drawAlerts(alerts) {
  alertLayer.clearLayers();
  const list = document.getElementById("alert-list");
  const count = document.getElementById("alert-count");
  count.textContent = alerts.length;
  count.classList.toggle("badge--zero", alerts.length === 0);
  list.innerHTML = "";

  if (alerts.length === 0) {
    list.innerHTML = '<li class="empty">Sin alertas en este momento</li>';
    return;
  }

  for (const a of alerts) {
    const line = L.polyline([[a.lat_a, a.lon_a], [a.lat_b, a.lon_b]], {
      color: COLORS.alert, weight: 3, dashArray: "6 6",
    }).bindTooltip(`${escapeHtml(a.train_a)} ↔ ${escapeHtml(a.train_b)}: ${a.distance_m} m`);
    alertLayer.addLayer(line);
    // Halo alrededor del punto medio para que se vea aunque la distancia sea 0
    alertLayer.addLayer(L.circle([(a.lat_a + a.lat_b) / 2, (a.lon_a + a.lon_b) / 2], {
      radius: Math.max(a.distance_m / 2, 300), color: COLORS.alert, weight: 1, fillOpacity: 0.08,
    }));

    const li = document.createElement("li");
    li.innerHTML = `<div class="pair">${escapeHtml(a.train_a)} ↔ ${escapeHtml(a.train_b)}</div>
      <div class="meta">${a.distance_m} m · umbral ${a.threshold_m} m · ${fmtTime(a.detected_at)}</div>`;
    li.addEventListener("click", () => map.flyTo([(a.lat_a + a.lat_b) / 2, (a.lon_a + a.lon_b) / 2], 14));
    list.appendChild(li);
  }
}

// ---------------------------------------------------------------------------
// Estado y estadísticas
// ---------------------------------------------------------------------------
function setStatus(kind, text) {
  const el = document.getElementById("status");
  el.className = `status status--${kind}`;
  el.textContent = text;
}

function updateStats(list) {
  const stopped = list.filter(t => t.status === "STOPPED_AT").length;
  document.getElementById("stat-total").textContent = list.length;
  document.getElementById("stat-moving").textContent = list.length - stopped;
  document.getElementById("stat-stopped").textContent = stopped;
}

// ---------------------------------------------------------------------------
// Ciclo principal
// ---------------------------------------------------------------------------
async function refresh() {
  try {
    const [list, alerts] = await Promise.all([
      getJSON("/getTrenes"),
      getJSON("/getAlertas?limit=200"),
    ]);
    const active = activeAlerts(alerts);
    const alertIds = new Set(active.flatMap(a => [a.train_a, a.train_b]));

    updateTrains(list, alertIds);
    drawAlerts(active);
    updateStats(list);

    if (list.length === 0) {
      setStatus("warn", "Sin datos recientes: el colector no ha guardado posiciones en los últimos minutos.");
    } else {
      setStatus("ok", `Actualizado a las ${new Date().toLocaleTimeString("es-ES")} · cada ${POLL_MS / 1000} s`);
    }
  } catch (err) {
    setStatus("error", `Servicio no disponible (${err.message}). Reintentando…`);
  }
}

refresh();
setInterval(refresh, POLL_MS);
