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
// Map
// ---------------------------------------------------------------------------
const map = { project: null, tracts: new Map(), sites: [], ready: null };

function nextMonth() {
  const d = new Date();
  const m = new Date(d.getFullYear(), d.getMonth() + 1, 1);
  return `${m.getFullYear()}-${String(m.getMonth() + 1).padStart(2, "0")}`;
}

async function loadMap() {
  const [geo, layers] = await Promise.all([
    fetch("/ui/fulton_tracts_2020.geojson").then((r) => r.json()),
    fetch("/api/map").then((r) => { if (!r.ok) throw new Error("map data unavailable"); return r.json(); }),
  ]);
  layers.tracts.forEach((t) => map.tracts.set(t.geo_id, t));
  map.sites = layers.sites;
  map.ranked = layers.tracts_ranked;
  $("county").textContent = `${layers.county} · mobile clinic`;
  drawMap(geo);
}

function drawMap(geo) {
  // Equirectangular with a cos(latitude) correction: at county scale it is indistinguishable
  // from a proper projection and needs no library.
  let minX = 180, maxX = -180, minY = 90, maxY = -90;
  const each = (coords, fn) => coords.forEach((ring) => ring.forEach(([x, y]) => fn(x, y)));
  geo.features.forEach((f) => {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    polys.forEach((p) => each(p, (x, y) => {
      minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }));
  });
  const k = Math.cos(((minY + maxY) / 2) * Math.PI / 180);
  const W = 520, scale = W / ((maxX - minX) * k), H = Math.round((maxY - minY) * scale);
  map.project = (lon, lat) => [((lon - minX) * k * scale).toFixed(1), ((maxY - lat) * scale).toFixed(1)];

  const svg = $("map");
  svg.setAttribute("viewBox", `-8 -8 ${W + 16} ${H + 16}`);
  svg.replaceChildren();
  const gT = svgEl("g"), gS = svgEl("g"), gV1 = svgEl("g", { id: "v1-layer" }), gP = svgEl("g", { id: "stop-layer" });

  geo.features.forEach((f) => {
    const id = f.properties.geo_id;
    const t = map.tracts.get(id);
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    const d = polys.map((p) => p.map((ring) => "M" + ring.map(([x, y]) => map.project(x, y).join(",")).join("L") + "Z").join("")).join("");
    const q = t ? Math.min(4, Math.floor((1 - (t.need_rank - 1) / map.ranked) * 5)) : null;
    const path = svgEl("path", { d, class: `tract ${t ? "q" + q : "na"}`, "data-id": id });
    gT.appendChild(path);
  });
  map.sites.filter((s) => s.safety_net).forEach((s) => {
    const [x, y] = map.project(s.lon, s.lat);
    const g = svgEl("g", { class: "site", transform: `translate(${x},${y})` });
    g.appendChild(svgEl("path", { d: "M0,-4V4M-4,0H4" }));
    g.appendChild(Object.assign(svgEl("title"), { textContent: `${s.name}${s.hours_per_week ? ` · ${Math.round(s.hours_per_week)} h/week` : ""}` }));
    gS.appendChild(g);
  });
  svg.append(gT, gS, gV1, gP);

  const tip = $("tip");
  const show = (e) => {
    const id = e.target.getAttribute?.("data-id");
    if (!id) { tip.hidden = true; return; }
    const t = map.tracts.get(id);
    tip.replaceChildren();
    tip.append(el("b", null, `Tract ${id}`));
    if (t) {
      tip.append(el("div", null, `Need rank ${t.need_rank} of ${map.ranked} · ${fmt(t.population)} people`));
      tip.append(el("div", null, `${t.pct_uninsured}% of adults 18-64 uninsured (modeled)`));
      tip.append(el("div", null, `${t.pct_no_vehicle}% of households without a car`));
      tip.append(el("div", null, `${t.km_to_safety_net} km to a safety-net clinic (straight line)`));
    } else {
      tip.append(el("div", null, "Under 500 people: not ranked"));
    }
    const box = svg.parentElement.getBoundingClientRect();
    const x = (e.clientX ?? 0) - box.left, y = (e.clientY ?? 0) - box.top;
    tip.style.left = `${Math.min(x + 14, box.width - 250)}px`;
    tip.style.top = `${y + 14}px`;
    tip.hidden = false;
  };
  svg.addEventListener("mousemove", show);
  svg.addEventListener("click", show);
  svg.addEventListener("mouseleave", () => { tip.hidden = true; });
}

function drawStops(stops, rejected) {
  const layer = $("stop-layer"), ghost = $("v1-layer");
  if (!layer || !map.project) return;
  layer.replaceChildren(); ghost.replaceChildren();
  rejected.forEach((id) => {
    const t = map.tracts.get(id);
    if (!t) return;
    const [x, y] = map.project(t.lon, t.lat);
    const g = svgEl("g", { class: "ghost-stop", transform: `translate(${x},${y})` });
    g.appendChild(svgEl("circle", { r: 10 }));
    g.appendChild(Object.assign(svgEl("text", { y: -14 }), { textContent: "v1" }));
    ghost.appendChild(g);
  });
  stops.forEach((s, i) => {
    const t = map.tracts.get(s.geo_id);
    if (!t) return;
    const [x, y] = map.project(t.lon, t.lat);
    const g = svgEl("g", { class: "stop", transform: `translate(${x},${y})` });
    g.appendChild(svgEl("circle", { r: 11 }));
    g.appendChild(Object.assign(svgEl("text"), { textContent: String(i + 1) }));
    layer.appendChild(g);
  });
  $("lg-v1").hidden = rejected.length === 0;
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
    const final = await fetch(`/apps/${APP}/users/${userId}/sessions/${session.id}`).then((r) => r.json());
    let flyer = "";
    try {
      const art = await fetch(`/apps/${APP}/users/${userId}/sessions/${session.id}/artifacts/flyers.html`).then((r) => r.json());
      const b64 = art.inlineData?.data || art.inline_data?.data;
      if (b64) flyer = new TextDecoder().decode(Uint8Array.from(atob(b64.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0)));
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
    c.append(el("span", "num", String(i + 1)));
    c.append(el("h3", null, s.saturday_en || s.saturday));
    const meta = el("p", "meta");
    meta.append("Tract ", el("b", null, s.geo_id), ` · ${fmt(s.population)} people · need rank ${s.need_rank} ${s.need_rank_note || ""}`);
    c.append(meta);
    const facts = el("div", "facts");
    const fact = (v, unit, label) => { const f = el("span", "fact"); f.append(el("b", null, `${v}${unit}`), " ", label); facts.append(f); };
    fact(s.pct_uninsured.value, "%", "uninsured adults 18-64");
    fact(s.pct_no_vehicle.value, "%", "households without a car");
    fact(s.km_to_safety_net.value, " km", "to a safety-net clinic");
    fact(s.pct_high_bp.value, "%", "high blood pressure");
    const tags = el("span", "fact"); tags.append(el("small", null, "tract-level · PLACES modeled · distances straight-line")); facts.append(tags);
    c.append(facts);
    if (s.refer_to) {
      const r = el("p", "refer");
      const hours = s.refer_to.hours_per_week ? `${Math.round(s.refer_to.hours_per_week)} h/week` : "hours not published";
      r.append(el("span", null, "Follow-up care: "), `${s.refer_to.display_name || s.refer_to.name}, ${s.refer_to.address} · ${hours}`);
      c.append(r);
    }
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
