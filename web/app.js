// Lagos Transit Tracker map.
// The API base defaults to "/api" (nginx in the web container proxies it to the api service).
// For testing against an API running elsewhere, open the page with ?api=http://localhost:8000
const API = new URLSearchParams(location.search).get("api") || "/api";
const POLL_MS = 3000;

const map = L.map("map", { zoomControl: true }).setView([6.54, 3.42], 12);
L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
}).addTo(map);

document.getElementById("api-link").href = `${API}/docs`;

const markers = new Map();   // bus id -> { marker, from, to, start }
let selectedStop = null;

async function getJSON(path) {
  const res = await fetch(`${API}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json();
}

function setState(ok, label) {
  const dot = document.getElementById("stat-state");
  dot.className = `dot ${ok ? "ok" : "bad"}`;
  document.getElementById("stat-state-label").textContent = label;
}

async function drawRoute() {
  const stops = await getJSON("/stops");
  const line = stops.map(s => [s.lat, s.lng]);
  L.polyline(line, { color: getComputedStyle(document.documentElement).getPropertyValue("--route").trim() || "#1d4ed8", weight: 5, opacity: 0.75 }).addTo(map);
  stops.forEach(s => {
    L.circleMarker([s.lat, s.lng], { radius: 6, color: "#fff", weight: 2, fillColor: "#1d2433", fillOpacity: 1 })
      .bindTooltip(s.name, { permanent: true, direction: "right", offset: [8, 0], className: "stop-label" })
      .on("click", () => chooseStop(s.name))
      .addTo(map);
  });
  map.fitBounds(L.latLngBounds(line).pad(0.15));
  const select = document.getElementById("stop");
  select.innerHTML = `<option value="">Choose a stop…</option>` + stops.map(s => `<option>${s.name}</option>`).join("");
  select.addEventListener("change", e => chooseStop(e.target.value));
}

function busIcon(b) {
  const cls = b.stale ? "stale" : (b.direction === "to CMS" ? "to-cms" : "to-ikd");
  return L.divIcon({ className: "", html: `<div class="bus ${cls}">🚌</div>`, iconSize: [26, 26], iconAnchor: [13, 13] });
}

function busTooltip(b) {
  return `<b>${b.id}</b> · ${b.direction}<br>${b.speed_kmh} km/h · next: ${b.next_stop}<br><small>${b.age_seconds}s ago${b.stale ? " · no signal" : ""}</small>`;
}

async function refreshBuses() {
  try {
    const buses = await getJSON("/buses");
    const now = performance.now();
    const seen = new Set();
    for (const b of buses) {
      seen.add(b.id);
      const target = [b.lat, b.lng];
      let m = markers.get(b.id);
      if (!m) {
        const marker = L.marker(target, { icon: busIcon(b) }).bindTooltip(busTooltip(b)).addTo(map);
        m = { marker, from: target, to: target, start: now };
        markers.set(b.id, m);
      } else {
        m.from = m.marker.getLatLng() ? [m.marker.getLatLng().lat, m.marker.getLatLng().lng] : target;
        m.to = target;
        m.start = now;
        m.marker.setIcon(busIcon(b));
        m.marker.setTooltipContent(busTooltip(b));
      }
    }
    for (const [id, m] of markers) if (!seen.has(id)) { map.removeLayer(m.marker); markers.delete(id); }

    const live = buses.filter(b => !b.stale);
    document.getElementById("stat-buses").textContent = live.length;
    const freshest = live.length ? Math.min(...live.map(b => b.age_seconds)) : null;
    document.getElementById("stat-fresh").textContent = freshest === null ? "–" : `${Math.round(freshest)}s`;
    setState(live.length > 0, live.length ? "live" : "no signal");
  } catch (e) {
    setState(false, "API down");
    console.error(e);
  }
  if (selectedStop) refreshEta();
}

// Glide each bus from its old position to the new one over the poll interval.
function animate() {
  const now = performance.now();
  for (const m of markers.values()) {
    const t = Math.min(1, (now - m.start) / POLL_MS);
    m.marker.setLatLng([m.from[0] + (m.to[0] - m.from[0]) * t, m.from[1] + (m.to[1] - m.from[1]) * t]);
  }
  requestAnimationFrame(animate);
}

function chooseStop(name) {
  selectedStop = name || null;
  document.getElementById("stop").value = name || "";
  refreshEta();
}

async function refreshEta() {
  const list = document.getElementById("eta");
  if (!selectedStop) { list.innerHTML = `<li class="muted">Pick a stop to see arriving buses</li>`; return; }
  try {
    const data = await getJSON(`/eta/${encodeURIComponent(selectedStop)}`);
    list.innerHTML = data.buses.length
      ? data.buses.map(b => `<li><div><b>${b.bus}</b><div class="meta">${b.direction} · ${b.km_away} km away</div></div><div class="mins">${b.eta_minutes < 1 ? "now" : Math.round(b.eta_minutes) + " min"}</div></li>`).join("")
      : `<li class="muted">No buses heading to ${data.stop} right now</li>`;
  } catch (e) {
    list.innerHTML = `<li class="muted">Couldn't load arrivals (API unreachable)</li>`;
  }
}

drawRoute()
  .catch(e => { setState(false, "API down"); console.error(e); })
  .finally(() => { refreshBuses(); setInterval(refreshBuses, POLL_MS); requestAnimationFrame(animate); });
