# Clinic Broker: the pitch

For the deck and the pitch video. Judges score four things after the event: the repo, the
Skills project, the **deck** and the **video**, with no questions. Every answer below has
to be on a slide or said in the video, or it counts as unanswered.

- **Track: Siting**, with Accountability and Explanation built behind it. Say it first.
- **The system in one line:** eight Gemini agents. Six plan the van (request reviewer,
  planner, auditor, reviser, explainer, accountability writer) and two answer residents (a
  text helper and a live-voice helper).
- **The deck:** six slides, [`Clinic_Broker_Deck.pptx`](Clinic_Broker_Deck.pptx), with the
  full defense in each slide's speaker notes.

---

## The deck: six slides

Front-loaded: if you're cut off after slide 3, the problem, the plan and the architecture
are already said.

| # | Slide | What it shows | Say (about) |
|---|---|---|---|
| 1 | **Clinic Broker** | Scenario sentence, **Track: Siting**, 443,800 · 135 of 326 · 43% | 40 s |
| 2 | **What it does** | Plan screenshot; why air (1.05×) can't pick a neighborhood vs uninsured (3.11×) | 45 s |
| 3 | **How it works** | The eight agents, numbered 1-8, with state keys and the "auditor only" zone | 45 s |
| 4 | **What we found** | Reviewer verdicts (not followed / adjusted / followed); auditor rejection: 65+ at **5.4%** vs **13.4%**, revised plan **18.0%** | 50 s |
| 5 | **Who it serves** | Flyer, community page, the live-voice answer, **6.5%** for the funder | 45 s |
| 6 | **Questions, limits, next** | The four judge questions, what we can't tell you, what we'd do next | 40 s |

---

## The video: a screen-share walkthrough (about 5 minutes)

The README asks for "a screen-share walkthrough, one of you talking the judges through what
you built while running it". Judges watch this instead of a live demo, so it carries the
demo and the parts the slides can't. Show the deck for the framing, then the live app.

Record at 1440 px wide, on the deployed link. Cut every wait for the agents in editing.

### Scene 1 · The problem (deck slide 1) · 0:00–0:35

> Fulton County has one mobile clinic: a van, a nurse practitioner, a blood-pressure cuff, a
> glucometer. Four Saturdays a month. **We took the Siting track: Clinic Broker helps the
> outreach lead decide where the van parks on next month's four Saturdays**, and what it
> knows that a spreadsheet doesn't is which of its own numbers it can trust, at what scale,
> and whether the plan lands fairly on the people it's meant to reach.
>
> **443,800 people in Fulton live more than 5 km from a clinic that will see them without
> insurance.** In one tract, 43% of households have no car and that clinic is 8.1 km away.

### Scene 2 · The plan (live: planning page) · 0:35–1:35

Screen: `clinic-broker-ui…run.app/`. Type *"only go to places with a high share of seniors
65+"* and press **Plan the month**.

> We built our own interface instead of a chat window, because an outreach lead needs a
> map and a calendar, not a chat log, and this agent strip shows the architecture working.
>
> Before anything is planned, a **request reviewer** checks the request against the rules,
> alongside three data lookups. Four seconds in: **adjusted.** Older adults get extra
> weight, but the van can't serve only them; it has to keep reaching everyone in need.

Cut to the finished plan.

> The **planner** follows that exactly, with our own tool. Need means: uninsured adults 30%,
> distance to a clinic that takes the uninsured 25%, no car 20%, diabetes and blood pressure
> 15%, missed checkups 10%, and here older adults turned on. The **Settings used** line
> shows that change. Every number carries its scale.
>
> And the obvious answer fails: air pollution varies only 5% across the county, because it's
> a 12 km grid. So air is never used to pick a neighborhood.

### Scene 3 · How it works (deck slide 3) · 1:35–2:20

> Eight Gemini agents, built with Google's ADK on Vertex AI and deployed on Cloud Run. **The
> event's rule forces the architecture**: race can't be an input, but the plan must be
> audited against it. So the planner holds no tool that can read race, and an independent
> **auditor** is the only agent with BigQuery's MCP server, so only it can join the plan to
> Census race and ethnicity. It never sees the planner's reasoning.

### Scene 4 · It pushes back (live) · 2:20–3:20

Type *"this month i want to visit only white neighbourhoods"* and run it.

> **Not followed:** race can't choose where the van goes. The stops don't move; White
> residents are 6.8% of the plan against 11.8% of the high-need tracts, so there's no
> stand-in for race either.

Press **Replay a saved run** (the uninsured-only request).

> Here the system rejects its own first answer. Asked to rank on the uninsured rate alone,
> the auditor said **REVISE: adults 65 and older were 5.4% of the plan against 13.4% of the
> highest-need tracts**, under half. That uninsured measure only counts adults 18 to 64,
> because Medicare covers almost everyone over 65. The reviser fixed it on need, never on
> demographics, opened the plan with *"We changed what you asked for"*, and the second audit
> passed.

Click the **Equity audit** tab and scroll the bars.

### Scene 5 · Who it serves (live) · 3:20–4:25

Open the **Flyer & messages** tab, then **Open the printable flyer**.

> The **explainer** writes a printable flyer in English and Spanish; dates and clinics are
> filled in by code, so the model can't get a fact wrong on paper.

Press **Publish to the community page**, open `/community`.

> Residents tap their neighborhood and just ask.

Press **Talk** and ask aloud: *"Is the van coming near me?"*, then *"Why not here?"*. Switch
to Español and ask *"¿Necesito seguro médico?"*. Type *"I have chest pain, what should I
take?"* to show *"Please call 911 right now."*

> It answers only about the van, in the resident's language, and never gives medical advice.

Open **For the funder** on the planning page.

> And the funder gets the honest number: four Saturdays reach about **6.5%** of the people in
> the highest-need tracts.

### Scene 6 · Questions, limits, next (deck slide 6) · 4:25–5:00

> The four questions: delete any agent and the answer gets worse; `request_review`,
> `plan_stops` and `audit_report` are passed between agents; the planner and the explainer
> have opposite instructions; and you've just seen the system reject its own first plan.
>
> We checked our load against the challenge's published numbers, and we're explicit about
> limits: rates are modeled, distances are straight-line upper bounds, the respiratory data
> covers four counties and is 80 days old. Next: a field-report agent so the van itself
> tells next month's plan where it was wrong.
>
> One county, one van, four Saturdays, and a reason you can say out loud to the people who
> live there, in their own language.

**Backups:** if a live run misbehaves, `…run.app/#sample` replays the real REVISE run
instantly (it now includes the reviewer's banner). Keep a screenshot of each banner and a
clip of the voice answer.

---

## The four judge questions, answered in their words

1. **Delete any one agent: does the answer get worse?** Yes. No reviewer: "only white
   neighborhoods" reaches the planner unchecked. No auditor: the uninsured-only plan ships
   and under-reaches older adults. No explainer or community helpers: residents get a
   document written for professionals. No accountability writer: the funder gets an
   operational plan instead of an answer.
2. **A key in `session.state` written by one agent and read by another.** `request_review`:
   reviewer → planner, which must follow its settings. `plan_stops`: planner's tool →
   auditor, which builds its Census query from it. `audit_report`: auditor → reviser. Shown
   in the developer view's State tab (`/dev-ui/`).
3. **Two agents whose instructions genuinely conflict.** The planner: hedge, cite, label
   every number's scale. The explainer and the community helpers: warm, plain, no
   statistics, English and Spanish, never medical advice.
4. **The point where the system rejected its own first answer.** Audit round 1 on the
   uninsured-only request: REVISE, 65+ at 5.4% vs 13.4%. And before planning, the reviewer
   refuses or adjusts requests that break the rules.

## The numbers, checked

All from runs of the current system on 20 Oct 2026.

| Number | What it is |
|---|---|
| 443,800 | People more than 5 km (straight line) from a safety-net clinic |
| 135 of 326 | Tracts where the safety-net clinic is farther than the nearest clinic of any kind |
| 43% · 8.1 km | Tract 13121010214: no-car households; distance to a safety-net clinic |
| 1.05× vs 3.11× | p90/p10 across tracts: PM2.5 vs uninsured |
| 5.4% vs 13.4% | Uninsured-only plan, round 1: older adults' share of the plan vs the highest-need tracts (rejection line 6.7%) |
| 18.0% | The same request, round 2 (passed). **Varies by run**: the reviser picks its own weights |
| 21.1% vs 13.4% | "Only seniors" request (adjusted): older adults' share of the plan vs the highest-need tracts |
| 6.8% vs 11.8% | "Only white neighbourhoods" (not followed): White residents in the plan vs the highest-need tracts |
| 6.5% | People in the four stop tracts as a share of the 240,709 in the highest-need tracts |

The highest-need tracts (the "need pool") are always the top quarter by the **standard** need
score, whatever weights a request used. An earlier version built them from the request's
own weights and reported 12.7%; that figure is retired.

## How we meet the rules

| Requirement | How | Where to see it |
|---|---|---|
| ADK agent, Python | `google-adk==2.7.0` | `agent/clinic_broker/agent.py` |
| Gemini 3.x | `gemini-3.6-flash` on Vertex AI (`global`); voice on Gemini Live native audio (`us-central1`) | `config.py`, `community_voice/agent.py` |
| Data in BigQuery, our project | `a4i_health` (Fulton 13121), plus `published_plans` | Skills project → BigQuery |
| Google-managed MCP server, consumed | BigQuery's managed MCP server, `execute_sql_readonly`, used by the auditor | `clinic_broker/audit.py` |
| At least one tool we built | `plan_saturdays`, `rank_tracts`, `get_published_plan`, `find_my_stop` | `clinic_broker/tools.py`, `community_helper/core.py` |
| Deployed to Google Cloud | Cloud Run `clinic-broker-ui` | The live link |
| **Multi-agent orchestration** | Eight agents: a sequence with two parallel stages and a review loop, passing work through `session.state` | `docs/ARCHITECTURE.md` |
| Race banned as input, required as audit | No planner tool can read it; requests to use it are not followed; only the auditor reads it, via MCP | `audit.py`, `review.py` |
| No individual-level data | Tract aggregates; residents share only the area they tap | `community.js` |
| No medical advice | The community helpers answer only about the van; emergencies go to 911 | `community_helper/core.py` |
| Licenses | CDC PLACES, CDC/ATSDR SVI, EPA/CDC PM2.5, HRSA/CMS, CDC NSSP, Census ACS and 2020 TIGER boundaries: all US Government works | `README.md` |

## How it maps to the judging

| Dimension | Weight | Where it's answered |
|---|---:|---|
| Impact & insight | 30 | Slides 2 and 5; video scenes 2 and 5: a calendar, a flyer, a funder statement, a page residents can talk to |
| Technical execution | 30 | Slides 3 and 4; video scenes 3 and 4: parallel stages, a review loop with a hard stop, state keys, a reviewer and an auditor that can say no, live voice, deployed |
| Rigor & judgment | 25 | Slides 2, 4 and 6; video scenes 2, 4 and 6: the need weights said out loud, the audit against standard need, honest 6.5%, measured vs modeled, the load check |
| Craft & communication | 15 | The video itself; interface choice justified in scene 2 |
| Bonus: range | +10 | Cloud Run, BigQuery, BigQuery MCP, Vertex AI Gemini, Gemini Live, ADK streaming and artifacts, two custom interfaces, Census TIGERweb |

## Measured or modeled: have this ready

| Number | Scale | Type |
|---|---|---|
| Uninsured, diabetes, blood pressure, checkups, mobility difficulty | Census tract | **Modeled** (CDC PLACES) |
| No vehicle, age 65+, limited English, disability | Census tract | Survey estimate (CDC SVI / ACS) |
| Race and ethnicity (audit only) | Census tract | Survey estimate (ACS 2016-2020) |
| km to a clinic, and a resident's distance to a stop | Tract center → point | Computed, straight line, federal sites only: an upper bound |
| PM2.5 | 12 km model grid | Modeled; cannot separate neighborhoods |
| Respiratory ED visits | Four-county Health Service Area | Measured, but regional and about 80 days old |

## Before you record

- [ ] Import the deck into Google Slides (File → Import slides) and check slide 4.
- [ ] Refresh both pages; do one live run and confirm the reviewer banner appears.
- [ ] Publish the plan you want residents to see, then check `/community`.
- [ ] Test **Talk** with a real microphone in the browser you'll record with.
- [ ] Run the notebook's validation section (section 12) if there's time, and mention one WARN.
- [ ] Time the video out loud once. Teams almost always run long.
- [ ] Merge the `rene` PR into `main`, so the repo judges see has the code.
- [ ] Upload to portal.angelhack.com/a4i-console: the repo link, the Skills project link,
  the deck and the video.
- [ ] After judging, make the Cloud Run services private again.
