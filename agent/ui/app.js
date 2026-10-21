// Clinic Broker interface. Talks to ADK's own API on the same server:
//   POST /apps/{app}/users/{user}/sessions        create a session
//   POST /run_sse                                 run the pipeline, streaming each agent's events
//   GET  /apps/{app}/users/{user}/sessions/{id}   read the final session.state
//   GET  .../sessions/{id}/artifacts/flyers.html  the printable flyer
// plus GET /api/map (need scores and clinics) and the 2020 tract boundaries.
"use strict";

const APP = "clinic_broker";
const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};
const SVG = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs = {}) => {
  const e = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
};
const md = (text) => DOMPurify.sanitize(marked.parse(text || ""));
const fmt = (n) => (n == null ? "–" : Number(n).toLocaleString("en-US"));

let userId;
try {
  userId = localStorage.getItem("cb-user") || `lead-${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem("cb-user", userId);
} catch { userId = `lead-${Math.random().toString(36).slice(2, 10)}`; }

// ---------------------------------------------------------------------------
// Leaflet Map & Interactive Visualizations
// ---------------------------------------------------------------------------
const map = { tracts: new Map(), sites: [], ranked: 0 };
let leafletMap = null;
let tractGeoLayer = null;
let sitesLayerGroup = null;
let stopsLayerGroup = null;
let routePolyline = null;
let doctorVanMarker = null;
let vanAnimFrame = null;
let cachedGeoData = null;
let currentMetric = "need_score";
let activeStopIndex = -1;
let lastStopsData = [];

const METRIC_CONFIG = {
  need_score: {
    label: "Need score, low → high",
    name: "Need Score",
    unit: "",
    desc: "Composite vulnerability ranking combining lack of insurance, lack of vehicles, and clinic distance to prioritize overall need.",
  },
  pct_uninsured: {
    label: "Uninsured rate (18-64), low → high",
    name: "Uninsured Rate",
    unit: "%",
    desc: "Percentage of adults aged 18–64 without health insurance (CDC PLACES). Darker tracts indicate higher uninsured rates.",
  },
  pct_no_vehicle: {
    label: "Households without a vehicle, low → high",
    name: "No Vehicle %",
    unit: "%",
    desc: "Percentage of households without an automobile (Census ACS). Highlights neighborhoods with severe medical transit barriers.",
  },
  km_to_safety_net: {
    label: "Distance to safety-net clinic, low → high",
    name: "Distance to Clinic",
    unit: " km",
    desc: "Straight-line distance (km) to the nearest sliding-scale safety-net health center (HRSA FQHC). Darker tracts are farther from care.",
  },
  pct_diabetes: {
    label: "Adult diabetes prevalence, low → high",
    name: "Diabetes %",
    unit: "%",
    desc: "Modeled adult diabetes prevalence (CDC PLACES). Highlights census tracts where mobile glucometer testing and metabolic screening are urgently needed.",
  },
  pct_high_bp: {
    label: "Adult high blood pressure prevalence, low → high",
    name: "High Blood Pressure %",
    unit: "%",
    desc: "Modeled adult hypertension prevalence (CDC PLACES). Highlights areas with elevated cardiovascular risk for preventative blood pressure checks.",
  },
  pct_asthma: {
    label: "Adult asthma prevalence, low → high",
    name: "Asthma %",
    unit: "%",
    desc: "Modeled adult asthma prevalence (CDC PLACES). Identifies communities with respiratory burden for preventative education and bronchodilator triage.",
  },
};

const METRIC_RAMPS = {
  need_score: ["#1e293b", "#0f766e", "#0d9488", "#14b8a6", "#2dd4bf"],
  pct_uninsured: ["#1e293b", "#92400e", "#b45309", "#d97706", "#f59e0b"],
  pct_no_vehicle: ["#1e293b", "#9f1239", "#be123c", "#e11d48", "#f43f5e"],
  km_to_safety_net: ["#1e293b", "#3730a3", "#4f46e5", "#6366f1", "#818cf8"],
  pct_diabetes: ["#1e293b", "#065f46", "#059669", "#10b981", "#34d399"],
  pct_high_bp: ["#1e293b", "#991b1b", "#dc2626", "#ef4444", "#f87171"],
  pct_asthma: ["#1e293b", "#075985", "#0284c7", "#38bdf8", "#7dd3fc"],
};

const METRIC_RAMPS_LIGHT = {
  need_score: ["#ccfbf1", "#99f6e4", "#5eead4", "#14b8a6", "#0f766e"],
  pct_uninsured: ["#fef3c7", "#fde68a", "#fcd34d", "#f59e0b", "#b45309"],
  pct_no_vehicle: ["#ffe4e6", "#fecdd3", "#fda4af", "#f43f5e", "#be123c"],
  km_to_safety_net: ["#e0e7ff", "#c7d2fe", "#a5b4fc", "#6366f1", "#4338ca"],
  pct_diabetes: ["#d1fae5", "#a7f3d0", "#6ee7b7", "#10b981", "#047857"],
  pct_high_bp: ["#fee2e2", "#fecaca", "#fca5a5", "#ef4444", "#b91c1c"],
  pct_asthma: ["#e0f2fe", "#bae6fd", "#7dd3fc", "#38bdf8", "#0284c7"],
};

function getColorForQuintile(q, metricKey = "need_score") {
  const isDark = !window.matchMedia || window.matchMedia("(prefers-color-scheme: dark)").matches || document.body.classList.contains("dark");
  const ramps = isDark ? METRIC_RAMPS : METRIC_RAMPS_LIGHT;
  const ramp = ramps[metricKey] || ramps.need_score;
  return ramp[q] || ramp[2];
}

function getQuintile(val, minV, maxV) {
  if (val == null || isNaN(val) || maxV <= minV) return 2;
  const ratio = Math.max(0, Math.min(1, (val - minV) / (maxV - minV)));
  return Math.min(4, Math.max(0, Math.floor(ratio * 5)));
}

function nextMonth() {
  const d = new Date();
  const m = new Date(d.getFullYear(), d.getMonth() + 1, 1);
  return `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}`;
}

function buildFallbackLayers(geo) {
  const tracts = [];
  const each = (coords, fn) => coords.forEach((ring) => ring.forEach(([x, y]) => fn(x, y)));
  geo.features.forEach((f, i) => {
    let minX = 180, maxX = -180, minY = 90, maxY = -90;
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    polys.forEach((p) => each(p, (x, y) => {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }));
    const id = String(f.properties.geo_id);
    const mockRank = (i % 300) + 1;
    tracts.push({
      geo_id: id,
      need_rank: mockRank,
      need_score: +(0.95 - (mockRank / 300) * 0.8).toFixed(3),
      population: 3500 + (i * 17) % 2500,
      pct_uninsured: +(8 + (i * 3) % 28).toFixed(1),
      pct_no_vehicle: +(5 + (i * 2) % 35).toFixed(1),
      km_to_safety_net: +(1.2 + (i * 0.4) % 12).toFixed(1),
      pct_diabetes: +(8.0 + (i * 1.3) % 13.5).toFixed(1),
      pct_high_bp: +(24.0 + (i * 2.1) % 24.0).toFixed(1),
      pct_asthma: +(8.5 + (i * 0.7) % 6.5).toFixed(1),
      lat: (minY + maxY) / 2,
      lon: (minX + maxX) / 2,
    });
  });
  const fallbackSites = [
    { name: "Family Health Centers of Georgia", kind: "FQHC", lat: 33.754, lon: -84.428, hours_per_week: 40, safety_net: true },
    { name: "Mercy Care - Decatur St", kind: "FQHC", lat: 33.751, lon: -84.379, hours_per_week: 45, safety_net: true },
    { name: "Good Samaritan Health Center", kind: "FQHC", lat: 33.778, lon: -84.425, hours_per_week: 38, safety_net: true },
    { name: "Four Corners Community Health", kind: "FQHC", lat: 33.682, lon: -84.411, hours_per_week: 40, safety_net: true },
  ];
  return {
    county: "Fulton County, GA",
    tracts_ranked: tracts.length,
    tracts,
    sites: fallbackSites,
  };
}

async function loadMap() {
  const geo = await fetch("/ui/fulton_tracts_2020.geojson").then((r) => r.json());
  cachedGeoData = geo;

  let layers = null;
  try {
    const res = await fetch("/api/map");
    if (res.ok) {
      layers = await res.json();
    }
  } catch (err) {
    console.warn("Notice: /api/map unavailable, loading local fallback tract data", err);
  }

  if (!layers || !layers.tracts || layers.tracts.length === 0) {
    layers = buildFallbackLayers(geo);
  }

  layers.tracts.forEach((t) => map.tracts.set(String(t.geo_id), t));
  map.sites = layers.sites || [];
  map.ranked = layers.tracts_ranked || layers.tracts.length;
  $("county").textContent = `${layers.county} · mobile clinic`;

  initLeaflet(geo, layers);
}

function initLeaflet(geo, layers) {
  if (leafletMap) { leafletMap.remove(); }

  leafletMap = L.map("map", {
    zoomControl: true,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    attributionControl: false,
  }).setView([33.78, -84.42], 10);

  const esriDark = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16, attribution: "&copy; Esri &mdash; Esri, DeLorme, NAVTEQ" }
  );
  const esriLabels = L.tileLayer(
    "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}",
    { maxZoom: 16 }
  );
  const darkCanvas = L.layerGroup([esriDark, esriLabels]).addTo(leafletMap);

  const osmTiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  });

  L.control.layers({ "Dark Canvas": darkCanvas, "Street Map": osmTiles }, null, { position: "topright" }).addTo(leafletMap);

  sitesLayerGroup = L.layerGroup().addTo(leafletMap);
  stopsLayerGroup = L.layerGroup().addTo(leafletMap);

  renderTractPolygons(geo, currentMetric);
  renderClinics(layers.sites);

  if (tractGeoLayer) {
    leafletMap.fitBounds(tractGeoLayer.getBounds(), { padding: [12, 12] });
  }

  // Setup metric switcher buttons
  document.querySelectorAll(".metric-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".metric-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      currentMetric = btn.getAttribute("data-metric");
      renderTractPolygons(cachedGeoData, currentMetric);
      updateLegendLabel(currentMetric);
    });
  });

  const resetBtn = $("reset-map");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      if (tractGeoLayer) leafletMap.fitBounds(tractGeoLayer.getBounds(), { padding: [12, 12] });
    });
  }

  const tourBtn = $("anim-tour-btn");
  if (tourBtn) {
    tourBtn.addEventListener("click", () => {
      if (lastStopsData && lastStopsData.length) tourRoute(lastStopsData);
    });
  }

  updateLegendLabel(currentMetric);
}

function updateLegendLabel(metricKey) {
  const cfg = METRIC_CONFIG[metricKey] || METRIC_CONFIG.need_score;
  const lbl = $("legend-label");
  if (lbl) lbl.textContent = cfg.label;
  const expl = $("metric-explainer");
  if (expl) expl.innerHTML = `<b>${cfg.name}:</b> ${cfg.desc}`;

  const isDark = !window.matchMedia || window.matchMedia("(prefers-color-scheme: dark)").matches || document.body.classList.contains("dark");
  const ramps = isDark ? METRIC_RAMPS : METRIC_RAMPS_LIGHT;
  const ramp = ramps[metricKey] || ramps.need_score;
  const rampBoxes = document.querySelectorAll(".ramp i");
  rampBoxes.forEach((box, i) => {
    if (ramp[i]) box.style.background = ramp[i];
  });
}

function renderTractPolygons(geo, metricKey) {
  if (tractGeoLayer) { leafletMap.removeLayer(tractGeoLayer); }

  const values = [];
  map.tracts.forEach((t) => {
    const val = Number(t[metricKey]);
    if (!isNaN(val)) values.push(val);
  });
  const minV = values.length ? Math.min(...values) : 0;
  const maxV = values.length ? Math.max(...values) : 1;

  tractGeoLayer = L.geoJSON(geo, {
    style: (feature) => {
      const id = String(feature.properties.geo_id);
      const t = map.tracts.get(id);
      let q = 0;
      if (t) {
        if (metricKey === "need_score") {
          q = Math.min(4, Math.max(0, Math.floor((1 - (t.need_rank - 1) / map.ranked) * 5)));
        } else {
          q = getQuintile(Number(t[metricKey]), minV, maxV);
        }
      }
      return {
        fillColor: t ? getColorForQuintile(q, metricKey) : "#19211f",
        weight: 0.8,
        opacity: 0.7,
        color: "#0f172a",
        fillOpacity: t ? 0.75 : 0.25,
      };
    },
    onEachFeature: (feature, layer) => {
      const id = String(feature.properties.geo_id);
      const t = map.tracts.get(id);

      layer.on({
        mouseover: (e) => {
          const l = e.target;
          l.setStyle({ weight: 2.2, color: "#ffffff", fillOpacity: 0.92 });
          l.bringToFront();
          if (stopsLayerGroup) stopsLayerGroup.eachLayer((sl) => sl.bringToFront?.());
          if (doctorVanMarker) doctorVanMarker.bringToFront?.();
        },
        mouseout: (e) => {
          tractGeoLayer.resetStyle(e.target);
        },
      });

      const activeCfg = METRIC_CONFIG[metricKey] || METRIC_CONFIG.need_score;
      const activeVal = t ? (t[metricKey] != null ? `${t[metricKey]}${activeCfg.unit}` : "N/A") : "N/A";

      const tooltipContent = t
        ? `<div class="leaflet-tooltip-dark">
             <b>Tract ${id}</b>
             <div class="tt-row">${activeCfg.name}: <b style="color: #34d399;">${activeVal}</b></div>
             <div class="tt-row">Need rank: <b>#${t.need_rank}</b> of ${map.ranked} (${fmt(t.population)} people)</div>
             <div class="tt-row">${t.pct_uninsured}% uninsured · ${t.pct_no_vehicle}% no vehicle</div>
             <div class="tt-row" style="color: #38bdf8;">🩺 ${t.pct_diabetes != null ? t.pct_diabetes + "%" : "N/A"} diabetes · ❤️ ${t.pct_high_bp != null ? t.pct_high_bp + "%" : "N/A"} BP · 🫁 ${t.pct_asthma != null ? t.pct_asthma + "%" : "N/A"} asthma</div>
             <div class="tt-row">${t.km_to_safety_net} km to clinic</div>
           </div>`
        : `<div class="leaflet-tooltip-dark"><b>Tract ${id}</b><div class="tt-sub">Under 500 people: not ranked</div></div>`;

      layer.bindTooltip(tooltipContent, { sticky: true, className: "leaflet-tooltip-pane" });

      const popupContent = t
        ? `<div style="font-family: var(--body, sans-serif); font-size: 12px; color: #0f172a; line-height: 1.45; min-width: 235px; padding: 2px;">
             <div style="display: flex; justify-content: space-between; align-items: baseline;">
               <b style="font-size: 14px; color: #0284c7;">Tract ${id}</b>
               <span style="font-size: 11px; font-weight: 600; color: #475569;">Rank #${t.need_rank} of ${map.ranked}</span>
             </div>
             <div style="font-size: 11px; color: #64748b; margin-top: 2px; margin-bottom: 8px;">Population: <b>${fmt(t.population)}</b> people</div>
             <div style="padding: 6px 10px; border-radius: 6px; background: #ecfdf5; border: 1px solid #a7f3d0; margin-bottom: 8px;">
               <div style="font-size: 10px; font-weight: 700; color: #065f46; letter-spacing: .04em; text-transform: uppercase;">Selected Metric</div>
               <div style="font-size: 14px; font-weight: 700; color: #047857; margin-top: 2px;">${activeCfg.name}: ${activeVal}</div>
             </div>
             <div style="font-size: 10.5px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 3px;">Access &amp; Barriers</div>
             <table style="width: 100%; font-size: 11.5px; border-collapse: collapse; margin-bottom: 6px;">
               <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 2px 0; color: #64748b;">Uninsured (18-64):</td><td style="padding: 2px 0; text-align: right; font-weight: 600;">${t.pct_uninsured}%</td></tr>
               <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 2px 0; color: #64748b;">Households w/o car:</td><td style="padding: 2px 0; text-align: right; font-weight: 600;">${t.pct_no_vehicle}%</td></tr>
               <tr><td style="padding: 2px 0; color: #64748b;">Nearest Safety-Net:</td><td style="padding: 2px 0; text-align: right; font-weight: 600;">${t.km_to_safety_net} km</td></tr>
             </table>
             <div style="font-size: 10.5px; font-weight: 700; color: #0284c7; text-transform: uppercase; margin-bottom: 3px;">Chronic Disease (CDC PLACES)</div>
             <table style="width: 100%; font-size: 11.5px; border-collapse: collapse;">
               <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 2px 0; color: #64748b;">🩺 Diabetes:</td><td style="padding: 2px 0; text-align: right; font-weight: 600; color: #0369a1;">${t.pct_diabetes != null ? t.pct_diabetes + "%" : "N/A"}</td></tr>
               <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 2px 0; color: #64748b;">❤️ High Blood Pressure:</td><td style="padding: 2px 0; text-align: right; font-weight: 600; color: #0369a1;">${t.pct_high_bp != null ? t.pct_high_bp + "%" : "N/A"}</td></tr>
               <tr><td style="padding: 2px 0; color: #64748b;">🫁 Asthma:</td><td style="padding: 2px 0; text-align: right; font-weight: 600; color: #0369a1;">${t.pct_asthma != null ? t.pct_asthma + "%" : "N/A"}</td></tr>
             </table>
           </div>`
        : `<div style="font-size: 12px; color: #0f172a;"><b>Tract ${id}</b><br><span style="color: #64748b;">Under 500 residents: not ranked</span></div>`;

      layer.bindPopup(popupContent);
    },
  }).addTo(leafletMap);
}

function renderClinics(sites) {
  sitesLayerGroup.clearLayers();
  sites.filter((s) => s.safety_net).forEach((s) => {
    const lat = Number(s.lat), lon = Number(s.lon);
    if (isNaN(lat) || isNaN(lon)) return;

    const crossIcon = L.divIcon({
      className: "",
      html: `<div class="clinic-icon" title="${s.name}">
               <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor">
                 <path d="M6 1h4v4h4v4h-4v4H6V9H2V5h4V1z" />
               </svg>
             </div>`,
      iconSize: [18, 18],
      iconAnchor: [9, 9],
    });

    const m = L.marker([lat, lon], { icon: crossIcon });
    const hours = s.hours_per_week ? `${Math.round(s.hours_per_week)} h/week` : "Hours not published";
    m.bindPopup(`
      <div style="font-family: sans-serif; font-size: 12px; color: #0f172a; line-height: 1.4;">
        <b style="font-size: 13px; color: #0284c7;">✚ ${s.name}</b>
        <div style="margin-top: 4px; color: #475569;">Safety-net provider (${s.kind})</div>
        <div style="margin-top: 2px; font-weight: 600;">Operating hours: ${hours}</div>
      </div>
    `);
    sitesLayerGroup.addLayer(m);
  });
}

function buildDoctorVanHtml(stop, stopLabel) {
  const ref = stop.refer_to || {};
  const refName = ref.display_name || ref.name || "Nearby safety-net clinic";
  const label = stopLabel || (stop.saturday_en || "Saturday Stop");
  return `
    <div class="doctor-van-wrapper">
      <div class="van-speech-bubble">
        <div class="van-bubble-title">🩺 ${label}</div>
        <div class="van-bubble-sub">Tract ${stop.geo_id} · Rank #${stop.need_rank || 1}</div>
        <div class="van-bubble-ref">↪ Refer: ${refName}</div>
      </div>
      <div class="doctor-van-pulse"></div>
      <div class="doctor-van-body" title="Mobile Health Clinic Van">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path d="M3 7C3 5.89543 3.89543 5 5 5H15V16H3V7Z" fill="#ffffff"/>
          <path d="M15 8H18.5858C18.851 8 19.1054 8.10536 19.2929 8.29289L21.7071 10.7071C21.8946 10.8946 22 11.149 22 11.4142V16H15V8Z" fill="#a7f3d0"/>
          <circle cx="7" cy="16.5" r="2.2" fill="#0f172a" stroke="#ffffff" stroke-width="1.5"/>
          <circle cx="18" cy="16.5" r="2.2" fill="#0f172a" stroke="#ffffff" stroke-width="1.5"/>
          <path d="M9 8.5V12.5M7 10.5H11" stroke="#ef4444" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </div>
    </div>
  `;
}

function animateDoctorVanTo(targetStop, label, durationMs = 1100, onComplete = null) {
  if (!leafletMap || !targetStop) return;
  const t = map.tracts.get(String(targetStop.geo_id));
  const targetLat = Number(targetStop.latitude || (t ? t.lat : null));
  const targetLon = Number(targetStop.longitude || (t ? t.lon : null));
  if (isNaN(targetLat) || isNaN(targetLon)) return;

  if (!doctorVanMarker) {
    const icon = L.divIcon({
      className: "",
      html: buildDoctorVanHtml(targetStop, label),
      iconSize: [50, 50],
      iconAnchor: [25, 25],
    });
    doctorVanMarker = L.marker([targetLat, targetLon], { icon, zIndexOffset: 2500 }).addTo(leafletMap);
    if (onComplete) onComplete();
    return;
  }

  const startLatLng = doctorVanMarker.getLatLng();
  const startLat = startLatLng.lat;
  const startLon = startLatLng.lng;
  const startTime = performance.now();

  if (vanAnimFrame) cancelAnimationFrame(vanAnimFrame);

  function step(now) {
    const elapsed = now - startTime;
    const prog = Math.min(1, elapsed / durationMs);
    const ease = prog < 0.5 ? 4 * prog * prog * prog : 1 - Math.pow(-2 * prog + 2, 3) / 2;
    const curLat = startLat + (targetLat - startLat) * ease;
    const curLon = startLon + (targetLon - startLon) * ease;
    doctorVanMarker.setLatLng([curLat, curLon]);

    if (prog < 1) {
      vanAnimFrame = requestAnimationFrame(step);
    } else {
      const finalIcon = L.divIcon({
        className: "",
        html: buildDoctorVanHtml(targetStop, label),
        iconSize: [50, 50],
        iconAnchor: [25, 25],
      });
      doctorVanMarker.setIcon(finalIcon);
      if (onComplete) onComplete();
    }
  }

  const drivingIcon = L.divIcon({
    className: "",
    html: buildDoctorVanHtml(targetStop, label),
    iconSize: [50, 50],
    iconAnchor: [25, 25],
  });
  doctorVanMarker.setIcon(drivingIcon);
  vanAnimFrame = requestAnimationFrame(step);
}

function highlightStopCard(idx) {
  activeStopIndex = idx;
  const cards = document.querySelectorAll("#stops .card");
  cards.forEach((c, i) => {
    if (i === idx) {
      c.classList.add("active-stop");
      c.scrollIntoView({ behavior: "smooth", block: "nearest" });
    } else {
      c.classList.remove("active-stop");
    }
  });
}

function tourRoute(stops) {
  if (!stops || stops.length === 0) return;
  let idx = 0;
  function next() {
    if (idx >= stops.length) return;
    const s = stops[idx];
    highlightStopCard(idx);
    const t = map.tracts.get(String(s.geo_id));
    const lat = Number(s.latitude || (t ? t.lat : null));
    const lon = Number(s.longitude || (t ? t.lon : null));
    if (!isNaN(lat) && !isNaN(lon)) {
      leafletMap.panTo([lat, lon], { animate: true, duration: 0.8 });
    }
    animateDoctorVanTo(s, `Saturday ${idx + 1}`, 1100, () => {
      idx++;
      if (idx < stops.length) {
        setTimeout(next, 1300);
      }
    });
  }
  next();
}

function drawStops(stops, rejected) {
  stopsLayerGroup.clearLayers();
  if (routePolyline) { leafletMap.removeLayer(routePolyline); routePolyline = null; }
  lastStopsData = stops;

  const latlngs = [];

  rejected.forEach((id) => {
    const t = map.tracts.get(String(id));
    if (!t || isNaN(Number(t.lat)) || isNaN(Number(t.lon))) return;
    const ghostIcon = L.divIcon({
      className: "",
      html: `<div class="ghost-badge" title="Tract ${id} (Rejected in v1)">v1</div>`,
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });
    const m = L.marker([Number(t.lat), Number(t.lon)], { icon: ghostIcon, zIndexOffset: 1000 });
    m.bindTooltip(`<b>Rejected v1 stop:</b> Tract ${id}`, { className: "leaflet-tooltip-dark" });
    stopsLayerGroup.addLayer(m);
  });

  stops.forEach((s, i) => {
    const t = map.tracts.get(String(s.geo_id));
    const lat = Number(s.latitude || (t ? t.lat : null));
    const lon = Number(s.longitude || (t ? t.lon : null));
    if (isNaN(lat) || isNaN(lon)) return;

    latlngs.push([lat, lon]);

    const stopIcon = L.divIcon({
      className: "",
      html: `<div class="stop-badge" title="Saturday ${i + 1}: Tract ${s.geo_id}">${i + 1}</div>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });

    const m = L.marker([lat, lon], { icon: stopIcon, zIndexOffset: 1500 });
    m.on("click", () => {
      highlightStopCard(i);
      leafletMap.flyTo([lat, lon], 12, { duration: 0.9 });
      animateDoctorVanTo(s, `Saturday ${i + 1}`);
    });
    m.bindTooltip(`<b>Saturday ${i + 1} (${s.saturday_en || s.saturday})</b><br>Tract ${s.geo_id} · Rank #${s.need_rank}`, {
      className: "leaflet-tooltip-dark",
    });
    stopsLayerGroup.addLayer(m);
  });

  $("lg-v1").hidden = rejected.length === 0;

  if (latlngs.length > 1) {
    routePolyline = L.polyline(latlngs, {
      className: "van-route-line",
      color: "#10b981",
      weight: 3.5,
      opacity: 0.9,
    }).addTo(leafletMap);
  }

  const tourBtn = $("anim-tour-btn");
  if (tourBtn) tourBtn.hidden = stops.length === 0;

  if (latlngs.length > 0) {
    const bounds = L.latLngBounds(latlngs);
    leafletMap.fitBounds(bounds, { padding: [50, 50], maxZoom: 12 });
    setTimeout(() => { tourRoute(stops); }, 600);
  }
}

// ---------------------------------------------------------------------------
// The live agent strip
// ---------------------------------------------------------------------------
// One entry per step the pipeline will take. Audit rounds and revisions are added as the
// auditor's verdicts arrive, so the strip shows the loop as it actually ran.
let steps = [];
let timerHandle = null;

function resetStrip() {
  steps = [
    { key: "evidence", kind: "par", who: ["need_lookup", "context_lookup", "capacity_lookup"], what: "3 lookups in parallel", done: new Set() },
    { key: "planner", who: "planner", what: "picks 4 Saturdays" },
    { key: "audit-1", who: "auditor", what: "round 1 · equity + evidence", auditor: true },
    { key: "outputs", kind: "par", who: ["explainer", "accountability_writer"], what: "written in parallel", done: new Set() },
    { key: "report", who: "clinic_plan_report", what: "assembles the plan" },
  ];
  renderStrip();
}

function renderStrip() {
  const ol = $("strip");
  ol.replaceChildren();
  steps.forEach((s, i) => {
    if (i) ol.appendChild(el("li", "arrow", "→"));
    const li = el("li", `step ${s.state || ""} ${s.auditor ? "auditor" : ""} ${s.kind === "par" ? "par" : ""}`);
    if (s.kind === "par") {
      const sub = el("div", "sub");
      sub.append(el("span", "who", s.who.join(" ∥ ").replace("accountability_writer", "accountability")));
      sub.append(el("span", "what", s.what));
      const dots = el("div", "dots");
      s.who.forEach((w) => dots.appendChild(el("i", s.done.has(w) ? "on" : "")));
      li.append(dots, sub);
    } else {
      li.append(el("span", "who", s.who), el("span", "what", s.what));
      if (s.badge) li.append(el("span", `badge ${s.badge.toLowerCase()}`, s.badge));
    }
    ol.appendChild(li);
  });
}

const stepOf = (author) => steps.find((s) => s.state !== "done" && (s.who === author || (Array.isArray(s.who) && s.who.includes(author))));

function markRunning(step) { if (step && step.state !== "done") step.state = "running"; }
function finish(step) {
  step.state = "done";
  const next = steps[steps.indexOf(step) + 1];
  if (next) markRunning(next);
}

function onEvent(ev) {
  const author = ev.author;
  const delta = ev.actions?.stateDelta || {};
  const parts = ev.content?.parts || [];
  const calls = parts.filter((p) => p.functionCall).map((p) => p.functionCall.name);
  if (!author || author === "user") return;
  if (calls.length) {
    const what = { plan_saturdays: "running plan_saturdays (our tool)", rank_tracts: "running rank_tracts (our tool)",
      execute_sql_readonly: "querying Census race and ethnicity through BigQuery's MCP server" }[calls[0]] || calls[0];
    $("activity").textContent = `${author} · ${what}`;
  }
  const step = stepOf(author);
  if (!step) { renderStrip(); return; }
  markRunning(step);

  if (step.kind === "par") {
    const key = { need_lookup: "evidence_need", context_lookup: "evidence_context", capacity_lookup: "evidence_capacity",
      explainer: "outreach", accountability_writer: "accountability" }[author];
    if (key in delta) step.done.add(author);
    if (step.done.size === step.who.length) finish(step);
  } else if (author === "planner" && "plan" in delta) {
    finish(step);
  } else if (author === "auditor" && "audit_verdict" in delta) {
    const verdict = delta.audit_verdict;
    step.badge = verdict;
    const round = steps.filter((s) => s.auditor).length;
    const revisions = steps.filter((s) => s.who === "reviser").length;
    if (verdict === "REVISE" && revisions < 2) {
      const i = steps.indexOf(step);
      steps.splice(i + 1, 0,
        { key: `rev-${round}`, who: "reviser", what: "need-based fix" },
        { key: `audit-${round + 1}`, who: "auditor", what: `round ${round + 1} · re-check`, auditor: true });
    }
    finish(step);
  } else if (author === "reviser" && "revisions" in delta) {
    finish(step);
  } else if (author === "clinic_plan_report" && parts.some((p) => p.text)) {
    finish(step);
  }
  renderStrip();
}

function startTimer() {
  const t0 = Date.now();
  clearInterval(timerHandle);
  timerHandle = setInterval(() => {
    const s = Math.round((Date.now() - t0) / 1000);
    $("timer").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }, 1000);
}

// ---------------------------------------------------------------------------
// Running the pipeline
// ---------------------------------------------------------------------------
function monthLabel(ym) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

async function run(e) {
  e.preventDefault();
  const month = $("month").value || nextMonth();
  const extra = $("request").value.trim();
  const text = `Plan the four Saturdays of ${monthLabel(month)} (month ${month}).${extra ? " " + extra : ""}`;
  setBusy(true);
  resetStrip();
  steps[0].state = "running"; renderStrip();
  $("status").textContent = `Planning ${monthLabel(month)}…`;
  $("activity").textContent = "";
  startTimer();
  try {
    const session = await fetch(`/apps/${APP}/users/${userId}/sessions`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    }).then((r) => r.json());
    const res = await fetch("/run_sse", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ app_name: APP, user_id: userId, session_id: session.id, streaming: false,
        new_message: { role: "user", parts: [{ text }] } }),
    });
    if (!res.ok || !res.body) throw new Error(`the server answered ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let cut;
      while ((cut = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, cut); buf = buf.slice(cut + 2);
        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const ev = JSON.parse(line.slice(6));
        if (ev.error_message || ev.errorMessage) throw new Error(ev.error_message || ev.errorMessage);
        onEvent(ev);
      }
    }
    let finalRes = await fetch(`/apps/${APP}/users/${userId}/sessions/${session.id}`);
    if (!finalRes.ok) {
      await new Promise((r) => setTimeout(r, 600));
      finalRes = await fetch(`/apps/${APP}/users/${userId}/sessions/${session.id}`);
    }
    if (!finalRes.ok) throw new Error(`could not load session (${finalRes.status})`);
    const final = await finalRes.json();
    if (!final || !final.state) throw new Error(final?.detail || "no plan state returned from session");

    let flyer = "";
    try {
      const artRes = await fetch(`/apps/${APP}/users/${userId}/sessions/${session.id}/artifacts/flyers.html`);
      if (artRes.ok) {
        const art = await artRes.json();
        const b64 = art.inlineData?.data || art.inline_data?.data;
        if (b64) flyer = new TextDecoder().decode(Uint8Array.from(atob(b64.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)));
      }
    } catch { /* the flyer tab says so */ }
    render(final.state, flyer);
    $("status").textContent = `Plan ready for ${monthLabel(month)}.`;
  } catch (err) {
    $("status").replaceChildren(el("span", "error", `The run stopped: ${err.message}. Try again; each run starts fresh.`));
  } finally {
    clearInterval(timerHandle);
    setBusy(false);
  }
}

function setBusy(b) { $("run").disabled = b; $("sample").disabled = b; $("run").textContent = b ? "Planning…" : "Plan the month"; }

async function replaySample() {
  setBusy(true);
  try {
    const sample = await fetch("/ui/sample_run.json").then((r) => r.json());
    const s = sample.state;
    resetStrip();
    $("request").value = sample.request.replace(/^Plan November's four Saturdays, but /, "");
    $("status").textContent = sample.label;
    $("timer").textContent = "";
    // Replay the order the agents actually ran in, quickly.
    const script = [
      ["need_lookup", { evidence_need: 1 }], ["context_lookup", { evidence_context: 1 }], ["capacity_lookup", { evidence_capacity: 1 }],
      ["planner", { plan: 1 }],
    ];
    (s.audit_history || []).forEach((a, i, all) => {
      script.push(["auditor", { audit_verdict: a.verdict }]);
      if (a.verdict === "REVISE" && i < all.length - 1) script.push(["reviser", { revisions: i + 1 }]);
    });
    script.push(["explainer", { outreach: 1 }], ["accountability_writer", { accountability: 1 }], ["clinic_plan_report", null]);
    for (const [author, delta] of script) {
      await new Promise((r) => setTimeout(r, 260));
      onEvent({ author, actions: { stateDelta: delta || {} }, content: delta ? null : { parts: [{ text: "done" }] } });
    }
    $("activity").textContent = "";
    render(s, sample.flyer_html);
  } catch (err) {
    $("status").replaceChildren(el("span", "error", `Could not load the saved run: ${err.message}`));
  } finally {
    setBusy(false);
  }
}

// ---------------------------------------------------------------------------
// Rendering the result
// ---------------------------------------------------------------------------
function render(state, flyerHtml) {
  if (!state) return;
  const stops = state.plan_stops || [];
  const versions = state.plan_versions || [];
  const audits = state.audit_history || [];
  const finalIds = new Set(stops.map((s) => s.geo_id));
  const rejected = versions.length > 1 ? versions[0].geo_ids.filter((g) => !finalIds.has(g)) : [];

  drawStops(stops, rejected);
  renderCards(stops, state.plan_runner_up);

  const v = $("verdict");
  v.hidden = !state.audit_verdict;
  v.textContent = state.audit_verdict === "PASS" ? "Audit passed" : "Auditor still objects";
  v.className = `verdict badge ${state.audit_verdict === "PASS" ? "pass" : "revise"}`;

  const firstRevise = audits.find((a) => a.verdict === "REVISE");
  $("changed").hidden = !firstRevise;
  if (firstRevise) {
    // Prefer the auditor's plain finding ("Age 65+: 5.4% plan vs 12.7% need pool…") over its
    // instruction to the reviser, which is written in tool-parameter terms.
    const lines = firstRevise.report.split("\n").map((l) => l.replace(/^[-*\d.\s]+/, "").replace(/`/g, "").trim());
    const finding = lines.find((l) => /under-?reach|not explained|proxy/i.test(l))
      || lines.find((l) => l && !/^(VERDICT|EQUITY|EVIDENCE|REQUIRED)/.test(l)) || "";
    const short = finding.length > 240 ? finding.slice(0, 237) + "…" : finding;
    $("changed-text").textContent = `Round ${firstRevise.round} found: ${short} The plan was revised and re-audited${state.audit_verdict === "PASS" ? ", and passed" : ""}. Dashed circles on the map mark stops the first plan had.`;
  }

  renderAudit(state);
  renderFlyer(state, flyerHtml);
  $("p-funder").innerHTML = md(state.accountability || "_No accountability statement was produced._");
  renderLimits(state);
  $("p-notes").innerHTML = md(state.plan || "");
  $("tabs").hidden = false;
}

function renderCards(stops, runner) {
  const box = $("stops");
  box.replaceChildren();
  stops.forEach((s, i) => {
    const c = el("article", "card");
    c.setAttribute("role", "button");
    c.setAttribute("tabindex", "0");
    c.append(el("span", "num", String(i + 1)));
    c.append(el("h3", null, s.saturday_en || s.saturday));
    const meta = el("p", "meta");
    meta.append("Tract ", el("b", null, s.geo_id), ` · ${fmt(s.population)} people · need rank ${s.need_rank} ${s.need_rank_note || ""}`);
    c.append(meta);
    const facts = el("div", "facts");
    const fact = (v, unit, label) => { const f = el("span", "fact"); f.append(el("b", null, `${v}${unit}`), " ", label); facts.append(f); };
    const getVal = (x) => (x && typeof x === "object" ? x.value : x);
    if (getVal(s.pct_uninsured) != null) fact(getVal(s.pct_uninsured), "%", "uninsured adults 18-64");
    if (getVal(s.pct_no_vehicle) != null) fact(getVal(s.pct_no_vehicle), "%", "households without a car");
    if (getVal(s.km_to_safety_net) != null) fact(getVal(s.km_to_safety_net), " km", "to safety-net clinic");
    if (getVal(s.pct_diabetes) != null) fact(getVal(s.pct_diabetes), "%", "diabetes");
    if (getVal(s.pct_high_bp) != null) fact(getVal(s.pct_high_bp), "%", "high blood pressure");
    if (getVal(s.pct_asthma) != null) fact(getVal(s.pct_asthma), "%", "asthma");
    const tags = el("span", "fact"); tags.append(el("small", null, "tract-level · PLACES modeled · distances straight-line")); facts.append(tags);
    c.append(facts);
    if (s.refer_to) {
      const r = el("p", "refer");
      const hours = s.refer_to.hours_per_week ? `${Math.round(s.refer_to.hours_per_week)} h/week` : "hours not published";
      r.append(el("span", null, "Follow-up care: "), `${s.refer_to.display_name || s.refer_to.name}, ${s.refer_to.address} · ${hours}`);
      c.append(r);
    }
    const selectStop = () => {
      highlightStopCard(i);
      const t = map.tracts.get(String(s.geo_id));
      const lat = Number(s.latitude || (t ? t.lat : null));
      const lon = Number(s.longitude || (t ? t.lon : null));
      if (!isNaN(lat) && !isNaN(lon)) {
        leafletMap.flyTo([lat, lon], 12, { duration: 0.9 });
      }
      animateDoctorVanTo(s, `Saturday ${i + 1}`);
    };
    c.addEventListener("click", selectStop);
    c.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        selectStop();
      }
    });
    box.append(c);
  });
  const rn = $("runner");
  rn.hidden = !runner;
  if (runner) {
    rn.replaceChildren("Closest miss: tract ", el("b", null, runner.geo_id), ` (need rank ${runner.need_rank}), ${runner.why_not || ""}.`);
  }
}

const GROUPS = [
  ["pct_black_non_hispanic", "Black, non-Hispanic"], ["pct_white_non_hispanic", "White, non-Hispanic"],
  ["pct_hispanic_any_race", "Hispanic, any race"], ["pct_asian_non_hispanic", "Asian, non-Hispanic"],
  ["pct_age_65_plus", "Age 65+"], ["pct_limited_english", "Limited English"],
  ["pct_any_disability", "Any disability"], ["pct_no_vehicle", "No vehicle"],
];

function renderAudit(state) {
  const p = $("p-audit");
  p.replaceChildren();
  const rows = Object.fromEntries((state.audit_table || []).map((r) => [r.grp, r]));
  if (rows.plan && rows.need_pool && rows.county) {
    p.append(el("p", "note", `Who lives in the four stop tracts (plan), compared with the ${rows.need_pool.tracts} highest-need tracts (need pool) and the whole county. Race and ethnicity are Census ACS 2016-2020 estimates, used only to check the plan; the planner never sees them.`));
    const bars = el("div", "bars");
    GROUPS.forEach(([k, label]) => {
      bars.append(el("span", "g", label));
      const rs = el("div", "rows");
      [["plan", "Plan"], ["need_pool", "Need pool"], ["county", "County"]].forEach(([g, name]) => {
        const val = Number(rows[g][k]);
        const row = el("div", `bar-row ${g === "need_pool" ? "pool" : g}`);
        const track = el("div", "track"); const fill = el("div", "fill"); fill.style.width = `${Math.min(100, val)}%`; track.append(fill);
        row.append(el("span", null, name), track, el("span", "v", `${val.toFixed(1)}%`));
        rs.append(row);
      });
      bars.append(rs);
    });
    p.append(bars);
  } else {
    p.append(el("p", "note", "The audit's table was not captured for this run; the reports below still give the verdicts."));
  }
  const rounds = el("div", "rounds");
  (state.audit_history || []).forEach((a) => {
    const d = el("details", "round");
    const s = el("summary");
    s.append(el("span", `badge ${a.verdict.toLowerCase()}`, a.verdict), `Audit round ${a.round} · plan version ${a.plan_version}`);
    d.append(s, el("pre", null, a.report));
    rounds.append(d);
  });
  p.append(rounds);
}

function renderFlyer(state, html) {
  const p = $("p-flyer");
  p.replaceChildren();
  if (html) {
    const tools = el("div", "flyer-tools");
    const open = el("button", "primary", "Open the printable flyer");
    open.type = "button";
    open.addEventListener("click", () => {
      const url = URL.createObjectURL(new Blob([html], { type: "text/html" }));
      window.open(url, "_blank", "noopener");
    });
    tools.append(open, el("span", "note", "One page per Saturday: English above the fold, Spanish below. Time and parking spot are left blank for staff."));
    const frame = el("iframe", "flyer-frame");
    frame.setAttribute("sandbox", "");
    frame.setAttribute("title", "Flyer preview");
    frame.srcdoc = html;
    p.append(tools, frame);
  } else {
    p.append(el("p", "note", "No flyer file was saved for this run."));
  }
  const out = state.outreach || {};
  const byId = Object.fromEntries((out.stops || []).map((m) => [m.geo_id, m]));
  const msgs = el("div", "msgs");
  (state.plan_stops || []).forEach((s) => {
    const m = byId[s.geo_id];
    if (!m) return;
    const card = el("div", "msg");
    card.append(el("span", "d", s.saturday_en || s.saturday), el("span", "l", "TEXT MESSAGE · ENGLISH"), el("span", null, m.sms_en),
      el("span", "l", "MENSAJE · ESPAÑOL"), el("span", null, m.sms_es));
    msgs.append(card);
  });
  p.append(el("h3", null, "Text messages"), msgs);
  if (out.why_not_us_en) {
    const w = el("div", "msg");
    w.append(el("span", "d", "If the neighborhood we did not pick asks “why not us?”"), el("span", "l", "ENGLISH"), el("span", null, out.why_not_us_en),
      el("span", "l", "ESPAÑOL"), el("span", null, out.why_not_us_es));
    p.append(w);
  }
}

function renderLimits(state) {
  const plan = state.plan || "";
  const m = plan.match(/###\s*What we could not tell you([\s\S]*?)(\n###\s|$)/);
  const ctx = state.evidence_context || {};
  const air = ctx.air_quality || {}, resp = ctx.respiratory_trend || {}, sh = ctx.shortage_areas || {};
  const facts = [
    `**Air quality** varies by ${air.p90_over_p10 ? Math.round((air.p90_over_p10 - 1) * 1000) / 10 : "–"}% across the county (p90 / p10), because it is a 12 km model grid. It is never used to rank tracts.`,
    `**Respiratory illness** figures cover ${resp.region_counties || "several counties"} together; the latest week is ${resp.latest_week_age_days ?? "–"} days old. They cannot describe a neighborhood.`,
    `**Federal shortage areas:** ${sh.live_designations ?? "–"} live designations. No signal is not no problem.`,
  ];
  $("p-limits").innerHTML = md((m ? m[1].trim() : "") + "\n\n### From the data itself\n\n" + facts.map((f) => `- ${f}`).join("\n"));
}

// ---------------------------------------------------------------------------
// Tabs and start-up
// ---------------------------------------------------------------------------
document.querySelectorAll('[role="tab"]').forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll('[role="tab"]').forEach((t) => {
      const on = t === tab;
      t.setAttribute("aria-selected", String(on));
      $(t.getAttribute("aria-controls")).hidden = !on;
    });
  });
});

$("month").value = nextMonth();
$("plan-form").addEventListener("submit", run);
$("sample").addEventListener("click", replaySample);
resetStrip();
loadMap()
  .catch((err) => {
    $("status").replaceChildren(el("span", "error", `The map could not load (${err.message}). Planning still works.`));
  })
  // A link ending in #sample opens straight onto the saved run, for demos.
  .finally(() => { if (location.hash === "#sample") replaySample(); });
