# Clinic Broker: the pitch

For the deck and the pitch video. Judges score the repo, the Skills project, the deck and
the video after the event, with no questions, so every answer below has to be **said or
shown**, not left for someone to ask. Plan for a short slot; the core script runs about
four minutes and the first two minutes stand on their own if you get cut off.

**Track: Siting**, with Accountability and Explanation built behind it. Say it in the first
slide.

**The system in one line:** eight Gemini agents. Six plan the van (request reviewer,
planner, auditor, reviser, explainer, accountability writer) and two answer residents (a
text helper and a live-voice helper).

---

## The script (about 4 minutes)

### 1. The decision (0:00–0:25)

> Fulton County has one mobile clinic: a van, a nurse practitioner, a blood-pressure cuff, a
> glucometer. Four Saturdays a month. Where it parks is a public health decision worth more
> than most of what happens inside it.
>
> **Clinic Broker helps the outreach lead in Fulton County decide where the van parks on
> next month's four Saturdays. And the thing it knows that a spreadsheet doesn't is which of
> its own numbers it can trust, at what scale, and whether the plan lands fairly on the
> people it's meant to reach.**

### 2. The number that matters, and the one that doesn't (0:25–1:00)

> **443,800 people in Fulton live more than 5 km from a clinic that will see them without
> insurance.** In 135 of the county's 326 tracts, the nearest clinic that takes the uninsured
> is farther than the nearest clinic of any kind. That's the gap a van closes.
>
> The obvious first answer is to send the van where the air is worst. But across all of
> Fulton, the dirtiest and cleanest tracts differ by **4.7%**: the air data is a 12 km grid
> wearing a tract ID. So the system uses air as county context and never to pick a street,
> and says so in every plan.

### 3. Demo: a plan, and a request it pushes back on (1:00–1:50)

Show the planning page (shot list below).

> The outreach lead types a request: *only go to places with a lot of seniors.* Before
> anything is planned, a **request reviewer** checks it against the rules, in parallel with
> three data lookups. Here's its verdict, four seconds in: **adjusted.** Older adults get
> extra weight, but the van can't serve only them, because it has to keep reaching everyone
> in need.
>
> The **planner** follows that exactly, using our own tool, and the route changes. Every
> number carries its scale, and the "Settings used" line shows what the request changed.
> Ask it to go only to white neighborhoods and the verdict is **not followed**: race can't
> choose where the van goes, and the plan doesn't move.

### 4. The rule that forced the architecture (1:50–2:40)

> The event's rule is that race can't be an input, but the plan must be audited against it.
> **That rule forces a separate agent.** The planner never sees race: no tool it holds can
> read it. An independent **auditor** is the only agent with BigQuery's MCP server, so only
> it can join the plan to Census race and ethnicity, and it can't see the planner's reasoning.
>
> And here's the system rejecting its own first answer. Asked to rank on the uninsured rate
> alone, the auditor said **REVISE: adults 65 and older were 5.4% of the plan against 12.7%
> of the high-need tracts**, because that uninsured measure only counts adults 18 to 64. The
> reviser fixed it on need, told the lead it changed what they asked for, and the second
> audit passed.

### 5. What the neighborhood gets (2:40–3:30)

> Two agents write for two very different readers. The **explainer** writes a printable
> flyer in English and Spanish, with dates and clinics filled in by code so the model can't
> get a fact wrong on paper. The lead presses **Publish**, and residents get a community
> page. They tap their neighborhood and just ask, out loud.

Play the live voice clip:

> *"Is the van coming near me?"* → "The van won't be in your neighborhood this month, but it
> will be stopping on Saturday, November 21st, about 5 kilometers away. No, you don't need
> insurance."
>
> *"¿Necesito seguro médico?"* → it answers in Spanish.

> It answers only about the van. Ask it about chest pain and it says: call 911.

### 6. For the funder, what we can't tell you, and close (3:30–4:10)

> The **accountability writer** answers the funder's question honestly: four Saturdays reach
> about **6.5%** of the people in the highest-need tracts.
>
> And we're explicit about limits. Distances are straight-line to federal clinics, so
> they're upper bounds. Disease rates are modeled, not counted. The respiratory data covers
> four counties and is 80 days old. Fulton has zero live federal shortage areas, and no
> signal isn't no problem.
>
> One county, one van, four Saturdays, and a reason you can say out loud to the people who
> live there, in their own language.

---

## Slides

Front-load: if you're cut off after slide 5, the core is already said.

| # | Slide | On the slide | Say |
|---|---|---|---|
| 1 | **Clinic Broker** | Track: Siting · Fulton County, GA · the one-sentence scenario | Section 1 |
| 2 | **The gap** | **443,800** people > 5 km from a clinic that takes the uninsured · 135 of 326 tracts | Section 2, first half |
| 3 | **The trap** | Air quality varies **4.7%** across the county (12 km grid) vs uninsured **3×** | Section 2, second half |
| 4 | **The plan** | Screenshot: map with four numbered stops, Saturday cards, the "Settings used" line | Section 3, first half |
| 5 | **The architecture** | The pipeline diagram from `docs/ARCHITECTURE.md`: reviewer and lookups in parallel → planner → audit loop → two writers, with the "auditor only" zone | Section 4, first half |
| 6 | **It checks the request** | Three banners: *not followed* (white neighborhoods) · *adjusted* (seniors only) · *followed* (leave out a tract) | Section 3, second half |
| 7 | **It rejected its own plan** | Plan v1 → REVISE (65+: 5.4% vs 12.7%) → reviser → Plan v2 → PASS, beside the equity bars | Section 4, second half |
| 8 | **For the neighborhood** | Flyer page (EN/ES) beside the community page with the voice transcript | Section 5 |
| 9 | **For the funder, and what we can't tell you** | The 6.5% line · the scale table: tract · 12 km grid · facility point · multi-county region | Section 6 |
| 10 | **The four judge questions** | The four answers below, one line each | Read them |

---

## The four judge questions, answered in their words

1. **Delete any one agent: does the answer get worse?** Yes. Without the request reviewer,
   "only white neighborhoods" or "only seniors" reaches the planner unchecked. Without the
   auditor, the uninsured-only plan ships and under-reaches older adults. Without the
   explainer and the community helpers, residents get a document written for professionals.
   Without the accountability writer, the funder gets an operational plan instead of an
   answer.
2. **Show me a key in `session.state` written by one agent and read by another.**
   `request_review`: written by the reviewer, read by the planner, which must follow its
   settings. `plan_stops`: written by the planner's tool, read by the auditor to build its
   Census query. `audit_report`: written by the auditor, read by the reviser. Show them in
   the developer view's State tab.
3. **Show me two agents whose instructions genuinely conflict.** The planner: hedge, cite,
   label every number with its scale. The explainer and the community helpers: warm, plain,
   no statistics, no hedging, English and Spanish, and never a word of medical advice. The
   reviewer can override what the lead asked; the auditor can override what the planner
   produced.
4. **Show me the point where your system rejected its own first answer.** Audit round 1 on
   the uninsured-only request: REVISE, 65+ at 5.4% vs 12.7%, shown live in the agent strip
   and the banner. And before planning, the reviewer refuses or adjusts requests that break
   the rules.

---

## Demo shot list (for the recording)

Record on the deployed link, 1440 px wide. Refresh both pages once before recording.

**Part A: the planning page** (`clinic-broker-ui…run.app/`)

| Screen | Action |
|---|---|
| Empty page | Show the month picker, the request box, the map shaded by need |
| Request box | Type *"only go to places with a high share of seniors 65+"* and press **Plan the month** |
| Agent strip | Four dots run in parallel; **hold on the amber "Request adjusted" banner** (about 4 s in) |
| While it runs | A live run takes 2–5 minutes: cut the wait in editing |
| Saturday cards | Read one card; point at the **Settings used** line (older adults 0.30) |
| Equity audit tab | Older adults 21.1% of the plan vs 13.4% of the need pool; audit passed |
| Second run (or cut to it) | *"this month i want to visit only white neighbourhoods"* → **purple "Request not followed"** banner; the stops don't move |
| **Replay a saved run** | The real REVISE run: auditor REVISE → reviser → PASS, red banner with the 65+ finding |
| Flyer tab | Open the printable flyer: English above the fold, Spanish below |
| For the funder tab | Highlight the 6.5% sentence |
| **Publish to the community page** | Press it; follow the link |
| `/dev-ui/` | Event graph and State tab: `request_review`, `plan_stops`, `audit_report` |

**Part B: the community page** (`…run.app/community`)

| Screen | Action |
|---|---|
| Page opens | The demo area is pre-selected: "not stopping in your neighborhood… closest stop Saturday, November 21, about 5.4 km away" |
| **Talk** | Ask out loud: *"Is the van coming near me?"* then *"Why not here?"* then *"Where can I go meanwhile?"* |
| Español | Switch the page to Spanish and ask *"¿Necesito seguro médico?"* |
| Chat box | Type *"I have chest pain, what should I take?"* → *"Please call 911 right now."* |

**Backup:** `…run.app/#sample` replays a real saved run instantly (it predates the request
reviewer, so it shows no reviewer banner). Keep screenshots of each banner and a recording
of the voice answer.

---

## How we meet the rules

| Requirement | How | Where to see it |
|---|---|---|
| ADK agent, Python | `google-adk==2.7.0` | `agent/clinic_broker/agent.py` |
| Gemini 3.x | `gemini-3.6-flash` on Vertex AI, location `global`; voice on Gemini Live native audio, `us-central1` | `config.py`, `community_voice/agent.py` |
| Data in BigQuery, our project | `a4i_health` (Fulton 13121), plus `published_plans` | Skills project → BigQuery |
| At least one Google-managed MCP server, consumed | BigQuery's managed MCP server, `execute_sql_readonly`, used by the auditor | `clinic_broker/audit.py` |
| At least one tool we built | `plan_saturdays`, `rank_tracts`, `get_published_plan`, `find_my_stop` | `clinic_broker/tools.py`, `community_helper/core.py` |
| Deployed to Google Cloud | Cloud Run `clinic-broker-ui` (and the ADK-only `clinic-broker`) | The live link |
| **Multi-agent orchestration (differentiator)** | Eight agents: a sequence with two parallel stages and a review loop, passing work through `session.state` | `docs/ARCHITECTURE.md` |
| Agents that genuinely coordinate and disagree | The reviewer can override the request; the auditor can reject the plan; the reviser must respond; the loop always ends on an audit | The banners and the REVISE run |
| Race banned as input, required as audit | No tool the planner holds can read it; requests to use it are not followed; only the auditor reads it, via MCP | "Who sees what" in `docs/ARCHITECTURE.md` |
| No individual-level data | Tract aggregates only; residents share only the area they tap; no names, addresses or health details | All tables, `community.js` |
| No medical advice | The community helpers answer only about the van; emergencies go to 911 | `community_helper/core.py` |
| Licenses | CDC PLACES, CDC/ATSDR SVI, EPA/CDC PM2.5, HRSA/CMS, CDC NSSP, Census ACS and 2020 TIGER boundaries: all US Government works | `README.md`, `agent/README.md` |
| Clinic Plan, four parts | Where and why · what we couldn't tell you · who it lands on · the neighborhood handout (plus the funder statement and the community page) | The interface |

## How it maps to the judging

| Dimension | Weight | Our answer |
|---|---:|---|
| Impact & insight | 30 | A dated calendar an outreach lead can use, a flyer to hand out, a statement for the funder, and a page where residents ask in their own language whether the van is coming near them |
| Technical execution | 30 | Real orchestration: parallel stages, a review loop with a hard stop, state keys passed between agents, a reviewer and an auditor that can say no, live voice over ADK's streaming API. Deployed, with two custom interfaces |
| Rigor & judgment | 25 | The need definition is ours and stated, with optional weights shown on screen. Every number carries its scale. Requests are judged against the rules, not a word list. The audit is reported pass or fail, against standard need. Coverage is honest at 6.5%. Defects found: 2010 vs 2020 tract boundaries, an 18-64-only uninsured measure, 80-day-old respiratory data |
| Craft & communication | 15 | Interfaces for the outreach lead and for residents instead of a chat log, with the architecture visible in the agent strip; a bilingual printable flyer; voice |
| Bonus: range | +10 | Cloud Run, BigQuery, BigQuery's managed MCP server, Vertex AI Gemini, **Gemini Live native audio**, ADK artifacts and streaming, two custom web interfaces, Census TIGERweb boundaries |

## Measured or modeled: have this ready

| Number | Scale | Type |
|---|---|---|
| Uninsured, diabetes, blood pressure, checkups, mobility difficulty | Census tract | **Modeled** (CDC PLACES) |
| No vehicle, age 65+, limited English, disability | Census tract | Survey estimate (CDC SVI / ACS) |
| Race and ethnicity (audit only) | Census tract | Survey estimate (ACS 2016-2020) |
| km to a clinic, and a resident's distance to a stop | Tract centre → point | Computed, straight line, federal sites only: an upper bound |
| PM2.5 | 12 km model grid | Modeled; cannot separate neighborhoods |
| Respiratory ED visits | Four-county Health Service Area | Measured, but regional and 80 days old |

## Before you record

- [ ] Refresh both pages; do one live run on the deployed planning page and confirm the
  reviewer banner appears.
- [ ] Publish the plan you want residents to see, then open `/community` and check it.
- [ ] Test **Talk** with a real microphone in the browser you'll record with.
- [ ] Run the notebook's validation section (section 12) and note one WARN worth a slide.
  Judges reward validation, and we loaded from the snapshot, so it has not been run yet.
- [ ] Time the script out loud once. Teams almost always run long.
- [ ] Merge the `rene` PR into `main`, so the repo judges see has the code.
- [ ] Upload to portal.angelhack.com/a4i-console: the repo link, the Skills project link,
  the deck and the video.
- [ ] After judging, make the Cloud Run services private again.
