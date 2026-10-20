// Community page. Residents tap their area, then ask by text or by voice.
//   text:  POST /run_sse                 app community_helper (gemini-3.6-flash)
//   voice: WebSocket /run_live           app community_voice (Gemini Live, native audio)
//   data:  GET /api/published, /api/my-stop, /api/map, and the 2020 tract boundaries
// The only location that leaves the page is the 11-digit area code of the tapped tract.
"use strict";

const $ = (id) => document.getElementById(id);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
const SVG = "http://www.w3.org/2000/svg";
const svgEl = (tag, attrs = {}) => { const e = document.createElementNS(SVG, tag); for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v); return e; };

const T = {
  en: {
    brand: "Free mobile clinic", county: "Fulton County Health Department",
    headline: "Is the free clinic van coming near you?",
    sub: "Free blood pressure and blood sugar checks with a nurse practitioner. You do not need insurance.",
    tap: "Tap your neighborhood on the map", lg_stop: "Van stop", lg_clinic: "Low-cost clinic", lg_you: "Your area",
    privacy: "Only the area you tap is sent to answer your questions. We never ask for your address or name.",
    your_area: "Your area", you_empty: "Tap the map to see the closest van stop and low-cost clinics.",
    ask: "Ask a question", talk: "Talk", stop_talk: "Stop", send: "Send", placeholder: "Type a question…",
    note: "This helper answers questions about the van's schedule and where to get care. It cannot give medical advice. In an emergency, call 911.",
    month: (m) => `Schedule for ${m}`, none_published: "This month's schedule is not posted yet.",
    here: (d) => `The van is coming to your neighborhood on <b>${d}</b>.`,
    near: (d, km) => `The van is not stopping in your neighborhood this month. The closest stop is <b>${d}</b>, about ${km} km away.`,
    clinics: "Low-cost clinics near you:", hours: (h) => (h ? `${h} hours a week` : "call for hours"),
    chips: ["Is the van coming near me?", "Do I need insurance?", "What does the van check?", "Why isn't it coming to my neighborhood?"],
    connecting: "Connecting…", listening: "Listening. Speak any time; tap Stop to end.", mic_denied: "The microphone is blocked. Allow it in your browser, or type instead.",
    voice_err: "Voice stopped. You can try again or type.", you_said: "You (voice)", helper: "Helper", thinking: "…",
    tapped_say: (id) => `(I just tapped my area on the map: area ${id}. Please use it for my neighborhood.)`,
  },
  es: {
    brand: "Clínica móvil gratis", county: "Departamento de Salud del Condado de Fulton",
    headline: "¿Viene la clínica móvil gratis cerca de usted?",
    sub: "Revisión gratis de la presión arterial y del azúcar con una enfermera practicante. No necesita seguro médico.",
    tap: "Toque su vecindario en el mapa", lg_stop: "Parada de la clínica", lg_clinic: "Clínica de bajo costo", lg_you: "Su zona",
    privacy: "Solo se envía la zona que usted toca, para responder sus preguntas. Nunca pedimos su dirección ni su nombre.",
    your_area: "Su zona", you_empty: "Toque el mapa para ver la parada más cercana y las clínicas de bajo costo.",
    ask: "Haga una pregunta", talk: "Hablar", stop_talk: "Parar", send: "Enviar", placeholder: "Escriba una pregunta…",
    note: "Esta ayuda responde preguntas sobre el horario de la clínica móvil y dónde recibir atención. No puede dar consejos médicos. En una emergencia, llame al 911.",
    month: (m) => `Horario de ${m}`, none_published: "El horario de este mes todavía no está publicado.",
    here: (d) => `La clínica móvil viene a su vecindario el <b>${d}</b>.`,
    near: (d, km) => `Este mes la clínica no para en su vecindario. La parada más cercana es el <b>${d}</b>, a unos ${km} km.`,
    clinics: "Clínicas de bajo costo cerca de usted:", hours: (h) => (h ? `${h} horas a la semana` : "llame para saber el horario"),
    chips: ["¿Viene la clínica cerca de mí?", "¿Necesito seguro médico?", "¿Qué revisa la clínica?", "¿Por qué no viene a mi vecindario?"],
    connecting: "Conectando…", listening: "Le escucho. Hable cuando quiera; toque Parar para terminar.", mic_denied: "El micrófono está bloqueado. Permítalo en su navegador, o escriba.",
    voice_err: "La voz se detuvo. Puede intentar de nuevo o escribir.", you_said: "Usted (voz)", helper: "Ayuda", thinking: "…",
    tapped_say: (id) => `(Acabo de tocar mi zona en el mapa: zona ${id}. Úsela para mi vecindario.)`,
  },
};
// A saved choice wins; otherwise follow the browser's language.
let lang = (navigator.language || "").toLowerCase().startsWith("es") ? "es" : "en";
try { lang = localStorage.getItem("cb-lang") || lang; } catch { /* keep the browser's */ }
const t = (k) => T[lang][k];

let userId;
try { userId = localStorage.getItem("cb-resident") || `res-${Math.random().toString(36).slice(2, 10)}`; localStorage.setItem("cb-resident", userId); }
catch { userId = `res-${Math.random().toString(36).slice(2, 10)}`; }

const state = { tract: "", plan: null, myStop: null, chatSession: null, project: null, sites: [] };

// ---------------------------------------------------------------------------
// Language
// ---------------------------------------------------------------------------
function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => { const v = T[lang][n.dataset.i18n]; if (typeof v === "string") n.textContent = v; });
  document.querySelectorAll("[data-i18n-ph]").forEach((n) => { n.placeholder = T[lang][n.dataset.i18nPh]; });
  document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
  $("talk-label").textContent = voice.on ? t("stop_talk") : t("talk");
  renderMonth(); renderYou(); renderChips();
}
document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => {
  lang = b.dataset.lang; try { localStorage.setItem("cb-lang", lang); } catch { /* fine */ } applyLang();
}));

function monthName(ym) {
  const [y, m] = ym.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(lang === "es" ? "es-US" : "en-US", { month: "long", year: "numeric" });
}
function renderMonth() {
  $("month-line").textContent = state.plan ? t("month")(monthName(state.plan.month)) : t("none_published");
}
function renderChips() {
  const box = $("chips"); box.replaceChildren();
  t("chips").forEach((q) => { const b = el("button", null, q); b.type = "button"; b.addEventListener("click", () => sendText(q)); box.append(b); });
}

// ---------------------------------------------------------------------------
// Map
// ---------------------------------------------------------------------------
async function loadMap() {
  const [geo, layers, plan] = await Promise.all([
    fetch("/ui/fulton_tracts_2020.geojson").then((r) => r.json()),
    fetch("/api/map").then((r) => r.json()),
    fetch("/api/published").then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  state.plan = plan; state.sites = layers.sites;
  const centroids = new Map(layers.tracts.map((x) => [x.geo_id, x]));
  let minX = 180, maxX = -180, minY = 90, maxY = -90;
  const polysOf = (f) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates);
  geo.features.forEach((f) => polysOf(f).forEach((p) => p.forEach((ring) => ring.forEach(([x, y]) => {
    minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
  }))));
  const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180), W = 520, s = W / ((maxX - minX) * k), H = Math.round((maxY - minY) * s);
  const P = (lon, lat) => [((lon - minX) * k * s).toFixed(1), ((maxY - lat) * s).toFixed(1)];
  const svg = $("cmap"); svg.setAttribute("viewBox", `-8 -8 ${W + 16} ${H + 16}`); svg.replaceChildren();
  const stopIds = new Set((plan?.stops || []).map((x) => x.geo_id));
  const gT = svgEl("g"), gS = svgEl("g"), gP = svgEl("g");
  geo.features.forEach((f) => {
    const id = f.properties.geo_id;
    const d = polysOf(f).map((p) => p.map((ring) => "M" + ring.map(([x, y]) => P(x, y).join(",")).join("L") + "Z").join("")).join("");
    const path = svgEl("path", { d, class: `ct ${stopIds.has(id) ? "stoptract" : ""}`, "data-id": id, tabindex: "-1" });
    gT.append(path);
  });
  layers.sites.filter((x) => x.safety_net).forEach((x) => {
    const [cx, cy] = P(x.lon, x.lat); const g = svgEl("g", { class: "site", transform: `translate(${cx},${cy})` });
    g.append(svgEl("path", { d: "M0,-4V4M-4,0H4" })); gS.append(g);
  });
  (plan?.stops || []).forEach((st, i) => {
    const c = centroids.get(st.geo_id); if (!c) return;
    const [cx, cy] = P(c.lon, c.lat); const g = svgEl("g", { class: "stop", transform: `translate(${cx},${cy})` });
    g.append(svgEl("circle", { r: 11 }), Object.assign(svgEl("text"), { textContent: String(i + 1) })); gP.append(g);
  });
  svg.append(gT, gS, gP);
  svg.addEventListener("click", (e) => { const id = e.target.getAttribute?.("data-id"); if (id) pickTract(id); });
  renderMonth();
}

async function pickTract(id) {
  if (state.tract === id) return;
  document.querySelectorAll(".ct.you").forEach((n) => n.classList.remove("you"));
  document.querySelector(`.ct[data-id="${id}"]`)?.classList.add("you");
  state.tract = id;
  try { state.myStop = await fetch(`/api/my-stop?geo_id=${id}`).then((r) => r.json()); } catch { state.myStop = null; }
  renderYou();
  if (voice.on && voice.ws?.readyState === 1) {
    voice.ws.send(JSON.stringify({ content: { role: "user", parts: [{ text: t("tapped_say")(id) }] } }));
  }
}

function renderYou() {
  const box = $("you-text");
  const m = state.myStop;
  if (!m || !m.found) { box.textContent = t("you_empty"); return; }
  const parts = [];
  if (m.closest_stop) {
    const d = lang === "es" ? m.closest_stop.saturday_es : m.closest_stop.saturday_en;
    parts.push(`<p>${m.van_comes_here ? t("here")(d) : t("near")(d, m.closest_stop.km_from_you)}</p>`);
  } else {
    parts.push(`<p>${t("none_published")}</p>`);
  }
  const esc = (x) => String(x ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const items = (m.closest_low_cost_clinics || []).map((c) =>
    `<li>${esc(c.name)} · ${esc(c.address)} · ${esc(t("hours")(c.hours_per_week && Math.round(c.hours_per_week)))} · ~${c.km_from_you} km</li>`).join("");
  if (items) parts.push(`<p>${t("clinics")}</p><ul>${items}</ul>`);
  box.innerHTML = parts.join("");
}

// ---------------------------------------------------------------------------
// Chat bubbles
// ---------------------------------------------------------------------------
function bubble(who, text, via) {
  const li = el("li", `msg-b ${who}`);
  if (via) li.append(el("span", "via", via));
  const body = el("span", "body", text); li.append(body);
  $("msgs").append(li); $("msgs").scrollTop = $("msgs").scrollHeight;
  return body;
}

// ---------------------------------------------------------------------------
// Text chat
// ---------------------------------------------------------------------------
async function sendText(q) {
  q = (q || "").trim(); if (!q) return;
  bubble("me", q);
  const wait = bubble("bot typing", t("thinking"));
  try {
    if (!state.chatSession) {
      state.chatSession = (await fetch(`/apps/community_helper/users/${userId}/sessions`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).then((r) => r.json())).id;
    }
    const res = await fetch("/run_sse", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ app_name: "community_helper", user_id: userId, session_id: state.chatSession, streaming: false,
        state_delta: { resident_tract: state.tract }, new_message: { role: "user", parts: [{ text: q }] } }),
    });
    const raw = await res.text();
    let answer = "";
    raw.split("\n").filter((l) => l.startsWith("data: ")).forEach((l) => {
      const ev = JSON.parse(l.slice(6));
      const txt = (ev.content?.parts || []).filter((p) => p.text && !p.thought).map((p) => p.text).join("");
      if (ev.author === "community_helper" && txt.trim()) answer = txt.trim();
    });
    wait.parentElement.classList.remove("typing");
    wait.textContent = answer || "…";
  } catch {
    wait.parentElement.classList.remove("typing");
    wait.textContent = lang === "es" ? "No pude responder. Intente de nuevo." : "I couldn't answer that. Please try again.";
  }
}
$("ask-form").addEventListener("submit", (e) => { e.preventDefault(); const q = $("ask-input").value; $("ask-input").value = ""; sendText(q); });

// ---------------------------------------------------------------------------
// Live voice: 16 kHz PCM up, 24 kHz PCM down, over ADK's /run_live websocket
// ---------------------------------------------------------------------------
const voice = { on: false, ws: null, stream: null, capCtx: null, playCtx: null, node: null, nextTime: 0, sources: [], userB: null, botB: null, pending: [] };

function b64FromBytes(u8) { let s = ""; for (let i = 0; i < u8.length; i += 0x8000) s += String.fromCharCode(...u8.subarray(i, i + 0x8000)); return btoa(s); }
function bytesFromB64(b64) { const bin = atob(b64.replace(/-/g, "+").replace(/_/g, "/")); const u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); return u8; }

function to16k(input, rate) {
  // Average-and-decimate resampling: plenty for speech going to a recognizer.
  const ratio = rate / 16000, n = Math.floor(input.length / ratio), out = new Int16Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.floor(i * ratio), b = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0; for (let j = a; j < b; j++) sum += input[j];
    const v = Math.max(-1, Math.min(1, sum / Math.max(1, b - a)));
    out[i] = v < 0 ? v * 0x8000 : v * 0x7fff;
  }
  return out;
}

function play(b64, mime) {
  const rate = Number((/rate=(\d+)/.exec(mime || "") || [])[1]) || 24000;
  const u8 = bytesFromB64(b64), pcm = new Int16Array(u8.buffer, u8.byteOffset, Math.floor(u8.byteLength / 2));
  const ctx = voice.playCtx, buf = ctx.createBuffer(1, pcm.length, rate), ch = buf.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 0x8000;
  const src = ctx.createBufferSource(); src.buffer = buf; src.connect(ctx.destination);
  const at = Math.max(ctx.currentTime + 0.03, voice.nextTime);
  src.start(at); voice.nextTime = at + buf.duration;
  voice.sources.push(src); src.onended = () => { voice.sources = voice.sources.filter((x) => x !== src); };
}
function stopPlayback() { voice.sources.forEach((s) => { try { s.stop(); } catch { /* already done */ } }); voice.sources = []; voice.nextTime = 0; }

function onLiveEvent(ev) {
  (ev.content?.parts || []).forEach((p) => { if (p.inlineData?.data && (p.inlineData.mimeType || "").startsWith("audio")) play(p.inlineData.data, p.inlineData.mimeType); });
  if (ev.interrupted) { stopPlayback(); voice.botB = null; }
  const it = ev.inputTranscription, ot = ev.outputTranscription;
  if (it?.text) {
    if (!voice.userB) voice.userB = bubble("me", "", t("you_said"));
    voice.userB.textContent = it.finished ? it.text.trim() : (voice.userB.textContent + it.text);
    if (it.finished) voice.userB = null;
  }
  if (ot?.text) {
    voice.userB = null;
    if (!voice.botB) voice.botB = bubble("bot", "", t("helper"));
    // Partial chunks arrive first, then the finished full text: keep the full one.
    voice.botB.textContent = ot.finished ? ot.text.trim() : (voice.botB.textContent + ot.text);
    if (ot.finished) voice.botB = null;
  }
  if (ev.turnComplete) voice.botB = null;
}

async function startVoice() {
  $("voice-status").textContent = t("connecting");
  try {
    voice.stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 } });
  } catch { $("voice-status").textContent = t("mic_denied"); return; }
  voice.on = true; $("talk").setAttribute("aria-pressed", "true"); $("talk-label").textContent = t("stop_talk");
  voice.playCtx = new AudioContext({ sampleRate: 24000 });
  voice.capCtx = new AudioContext();
  await voice.capCtx.audioWorklet.addModule("/ui/pcm-worklet.js");
  const src = voice.capCtx.createMediaStreamSource(voice.stream);
  voice.node = new AudioWorkletNode(voice.capCtx, "pcm-capture");
  const mute = voice.capCtx.createGain(); mute.gain.value = 0;
  src.connect(voice.node); voice.node.connect(mute); mute.connect(voice.capCtx.destination);

  const session = await fetch(`/apps/community_voice/users/${userId}/sessions`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ state: { resident_tract: state.tract } }) }).then((r) => r.json());
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  voice.ws = new WebSocket(`${proto}//${location.host}/run_live?app_name=community_voice&user_id=${userId}&session_id=${session.id}&modalities=AUDIO`);
  let chunk = []; let size = 0;
  voice.node.port.onmessage = (e) => {
    if (!voice.ws || voice.ws.readyState !== 1) return;
    chunk.push(e.data); size += e.data.length;
    if (size < voice.capCtx.sampleRate / 10) return; // send about every 100 ms
    const all = new Float32Array(size); let o = 0; chunk.forEach((c) => { all.set(c, o); o += c.length; }); chunk = []; size = 0;
    const pcm = to16k(all, voice.capCtx.sampleRate);
    voice.ws.send(JSON.stringify({ blob: { mimeType: "audio/pcm;rate=16000", data: b64FromBytes(new Uint8Array(pcm.buffer)) } }));
  };
  voice.ws.onopen = () => { $("voice-status").textContent = t("listening"); };
  voice.ws.onmessage = (m) => { try { onLiveEvent(JSON.parse(m.data)); } catch { /* ignore a malformed frame */ } };
  voice.ws.onclose = (e) => { if (voice.on) { $("voice-status").textContent = e.code === 1000 ? "" : t("voice_err"); stopVoice(); } };
  voice.ws.onerror = () => { $("voice-status").textContent = t("voice_err"); };
}

function stopVoice() {
  voice.on = false; $("talk").setAttribute("aria-pressed", "false"); $("talk-label").textContent = t("talk");
  try { voice.ws?.close(1000); } catch { /* closed */ }
  voice.stream?.getTracks().forEach((tr) => tr.stop());
  stopPlayback();
  voice.capCtx?.close(); voice.playCtx?.close();
  Object.assign(voice, { ws: null, stream: null, capCtx: null, playCtx: null, node: null, userB: null, botB: null });
  if ($("voice-status").textContent === t("listening") || $("voice-status").textContent === t("connecting")) $("voice-status").textContent = "";
}

$("talk").addEventListener("click", () => (voice.on ? stopVoice() : startVoice().catch(() => { $("voice-status").textContent = t("voice_err"); stopVoice(); })));

// For the demo the page opens on one real area: the challenge's own example, where 43% of
// households have no car and the nearest clinic that sees the uninsured is 8.1 km away.
// Tapping the map still picks any other area, and #area=<11 digits> overrides it.
const DEMO_AREA = "13121010214";

applyLang();
loadMap()
  .catch(() => { $("month-line").textContent = t("none_published"); })
  .finally(() => { const m = /area=(\d{11})/.exec(location.hash); pickTract(m ? m[1] : DEMO_AREA); });
