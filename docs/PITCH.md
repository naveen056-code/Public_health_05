# Clinic Broker: the pitch

For the deck and the pitch video. Judges score the repo, the Skills project, the deck and
the video after the event, with no questions, so every answer below has to be **said or
shown**, not left for someone to ask. Plan for a short slot; the core script runs about
four minutes and the first two minutes stand on their own if you get cut off.

**Track: Siting**, with Accountability and Explanation built behind it. Say it in the first
slide.

---

## The script (about 4 minutes)

### 1. The decision (0:00–0:30)

> Fulton County has one mobile clinic: a van, a nurse practitioner, a blood-pressure cuff, a
> glucometer. Four Saturdays a month. Where it parks is a public health decision worth more
> than most of what happens inside it. Park it in the wrong neighborhood and you've run an
> expensive health fair for people who already have a doctor.
>
> **Clinic Broker helps the outreach lead in Fulton County decide where the van parks on
> next month's four Saturdays. And the thing it knows that a spreadsheet doesn't is which of
> its own numbers it can trust, at what scale, and whether the plan lands fairly on the
> people it's meant to reach.**

### 2. The number that matters, and the one that doesn't (0:30–1:10)

> **443,800 people in Fulton live more than 5 km from a clinic that will see them without
> insurance.** In 135 of the county's 326 tracts, the nearest clinic that takes the uninsured
> is farther than the nearest clinic of any kind. That's the gap a van closes.
>
> The obvious first answer is to send the van where the air is worst. But across all of
> Fulton, the dirtiest and cleanest tracts differ by **4.7%**. The air data is a 12 km grid
> wearing a tract ID. So our system uses air quality as county context and never to pick a
> neighborhood, and it says so in every plan.

### 3. Demo: one plan (1:10–2:20)

Show the interface (see the shot list below). While it runs:

> Three lookups run in parallel: need, context and clinic capacity. Then the **planner**
> picks four Saturdays using our own tool, which ranks tracts on uninsured adults, distance
> to a safety-net clinic, households without a car, diabetes and blood pressure, and missed
> checkups, and keeps the stops 5 km apart. Every number it writes carries its scale.
>
> Here are the four stops on the map. Saturday, November 7: tract 13121007604. A third of
> households have no car, it's 4.6 km to a clinic that sees the uninsured, and follow-up
> care goes to the Family Health Centers of Georgia.

### 4. The rule that forced the architecture (2:20–3:10)

> The event's rule is that race can't be an input, but the plan must be audited against it.
> **That rule forces a second agent.** The planner never sees race: no tool it holds can read
> it. An independent **auditor** is the only agent with BigQuery's MCP server, so only it can
> join the plan to Census race and ethnicity. It runs with no access to the planner's
> reasoning, so it can't be talked into defending the plan.
>
> And here's where the system rejected its own first answer. The outreach lead asked: rank
> only on the uninsured rate, that's what our funder cares about. The auditor said
> **REVISE: adults 65 and older were 5.4% of the plan, against 12.7% of the high-need
> tracts.** Why? That uninsured measure only counts adults 18 to 64, because Medicare covers
> almost everyone over 65. Rank on it alone and older neighborhoods drop out. The reviser
> fixed it on need, never by picking tracts by demographics, told the lead up front that it
> changed what they asked for, and the second audit passed.

### 5. What the neighborhood and the funder get (3:10–3:40)

> Two more agents write for two very different readers, in parallel. The **explainer**
> writes a printable flyer, one page per Saturday, in English and Spanish, warm and plain,
> with no statistics. The dates, clinic names and hours on it are filled in by code, so the
> model can't get a fact wrong on paper. The **accountability writer** answers the funder's
> question, did the money go where the need was, and it's honest: **four Saturdays reach
> about 6.5% of the people in the highest-need tracts.**

### 6. What we can't tell you, and close (3:40–4:10)

> We're explicit about limits. Distances are straight-line to federal clinics only, so
> they're upper bounds. Disease rates are modeled estimates, not counts. The respiratory data
> covers four counties and is 80 days old, so it can't describe a street. Fulton has zero
> live federal shortage areas, and no signal isn't no problem.
>
> One county, one van, four Saturdays, and a reason you can say out loud to the people who
> live there.

---

## Slides

Front-load: if you're cut off after slide 4, the core is already said.

| # | Slide | On the slide | Say |
|---|---|---|---|
| 1 | **Clinic Broker** | Track: Siting · Fulton County, GA · the one-sentence scenario | Section 1 |
| 2 | **The gap** | **443,800** people > 5 km from a clinic that takes the uninsured · 135 of 326 tracts | Section 2, first half |
| 3 | **The trap** | Air quality varies **4.7%** across the county (12 km grid) vs uninsured **3×** | Section 2, second half |
| 4 | **The plan** | Screenshot: map with four numbered stops + Saturday cards | Section 3 |
| 5 | **The architecture** | The pipeline diagram from `docs/ARCHITECTURE.md`, with the "auditor only" zone | Section 4, first half |
| 6 | **It rejected its own plan** | Plan v1 → REVISE (65+: 5.4% vs 12.7%) → reviser → Plan v2 → PASS | Section 4, second half |
| 7 | **Who it lands on** | The equity bars: plan vs need pool vs county | One line: the audit result is reported pass or fail |
| 8 | **For the neighborhood and the funder** | Flyer page (EN/ES) beside the funder statement's 6.5% line | Section 5 |
| 9 | **What we can't tell you** | Scale table: tract · 12 km grid · facility point · multi-county region; measured vs modeled | Section 6 |
| 10 | **The four judge questions** | The four answers below, one line each | Read them |

---

## The four judge questions, answered in their words

1. **Delete any one agent: does the answer get worse?** Yes. Without the auditor, the
   uninsured-only plan ships and under-reaches older adults. Without the explainer, the
   neighborhood gets a document written for professionals. Without the accountability
   writer, the funder gets an operational plan instead of an answer.
2. **Show me a key in `session.state` written by one agent and read by another.**
   `plan_stops`: written by the planner's `plan_saturdays` tool, read by the auditor to
   build its Census query. `audit_report`: written by the auditor, read by the reviser.
   Show both in the developer view's State tab.
3. **Show me two agents whose instructions genuinely conflict.** The planner: hedge, cite,
   label every number with its scale. The explainer: warm, plain, sixth-grade, no
   statistics, no hedging, English and Spanish. One prompt cannot hold both.
4. **Show me the point where your system rejected its own first answer.** Audit round 1 on
   the uninsured-only request: REVISE, 65+ at 5.4% vs 12.7%. Shown live in the agent strip
   and in the red banner.

---

## Demo shot list (for the recording)

Record on the deployed link, after making it public. Keep the browser at 1440 px wide.

| Time | Screen | Action |
|---|---|---|
| 0:00 | `clinic-broker-ui…run.app/` | Show the empty page: month picker, request box, map shaded by need |
| 0:10 | Same | Type *"rank only on the uninsured rate, that's what our funder cares about"* and press **Plan the month** |
| 0:15 | Agent strip | Narrate the parallel lookups and the planner while it runs. A live run takes 2–5 minutes: cut the wait in editing, or switch to `#sample` |
| — | Agent strip | **Hold on the auditor turning REVISE**, then the reviser, then PASS |
| — | Red banner + map | Point at the banner's 65+ finding and the dashed circles for the rejected first plan |
| — | Saturday cards | Read one card: date, tract, the three numbers, follow-up clinic |
| — | Equity audit tab | Scroll the bars: plan vs need pool vs county |
| — | Flyer tab | Open the printable flyer: English above the fold, Spanish below |
| — | For the funder tab | Highlight the 6.5% sentence |
| — | `/dev-ui/` | Show the event graph and the State tab: `plan_stops` and `audit_report` |

**Backup:** if a live run misbehaves, `…run.app/#sample` replays a real saved run instantly.
Keep a screenshot of the finished page too.

---

## How we meet the rules

| Requirement | How | Where to see it |
|---|---|---|
| ADK agent, Python | `google-adk==2.7.0` | `agent/clinic_broker/agent.py` |
| Gemini 3.x | `gemini-3.6-flash` on Vertex AI, location `global` | `agent/clinic_broker/config.py` |
| Data in BigQuery, our project | `a4i_health`, Fulton 13121 | Skills project → BigQuery |
| At least one Google-managed MCP server, consumed | BigQuery's managed MCP server, `execute_sql_readonly`, used by the auditor | `agent/clinic_broker/audit.py` |
| At least one tool we built | `plan_saturdays`, `rank_tracts` | `agent/clinic_broker/tools.py` |
| Deployed to Google Cloud | Cloud Run `clinic-broker-ui` (and the ADK-only `clinic-broker`) | The live link |
| **Multi-agent orchestration (differentiator)** | 5 Gemini agents in a sequence with two parallel stages and a review loop, passing work through `session.state` | `docs/ARCHITECTURE.md` |
| Agents that genuinely coordinate and disagree | Auditor can reject the planner; reviser must respond; the loop always ends on an audit | The REVISE run |
| Race banned as input, required as audit | Planner's tools can't read it; only the auditor can, via MCP | "Who sees what" table |
| No individual-level data | Tract-level aggregates only; no names, addresses of people, or patient data | All tables |
| Licenses | CDC PLACES (public domain), CDC/ATSDR SVI, EPA/CDC PM2.5, HRSA/CMS, CDC NSSP, Census ACS and 2020 TIGER boundaries: all US Government works | `README.md`, `agent/README.md` |
| Clinic Plan, four parts | Where and why · what we couldn't tell you · who it lands on · the neighborhood handout (plus the funder statement) | The interface tabs |

## How it maps to the judging

| Dimension | Weight | Our answer |
|---|---:|---|
| Impact & insight | 30 | A dated calendar an outreach lead can use: four named tracts, the reasons, and where to send people afterwards. Plus the flyer to hand out and the statement for the funder |
| Technical execution | 30 | Real orchestration: parallel stages, a review loop with a hard stop, state keys passed between agents, an auditor that can say no. Deployed, with a custom interface that shows the agents working |
| Rigor & judgment | 25 | The need definition is ours and stated. Every number carries its scale. Measured vs modeled is labelled. The audit is reported pass or fail. Coverage is honest at 6.5%. Defects found: 2010 vs 2020 tract boundaries, an 18-64-only uninsured measure, 80-day-old respiratory data |
| Craft & communication | 15 | An interface for the outreach lead instead of a chat log, with the architecture visible in the agent strip; a bilingual printable flyer |
| Bonus: range | +10 | Cloud Run, BigQuery, BigQuery's managed MCP server, Vertex AI Gemini, ADK artifacts, a custom web interface, Census TIGERweb boundaries |

## Measured or modeled: have this ready

| Number | Scale | Type |
|---|---|---|
| Uninsured, diabetes, blood pressure, checkups | Census tract | **Modeled** (CDC PLACES) |
| No vehicle, age 65+, limited English, disability | Census tract | Survey estimate (CDC SVI / ACS) |
| Race and ethnicity (audit only) | Census tract | Survey estimate (ACS 2016-2020) |
| km to a clinic | Tract centre → facility point | Computed, straight line, federal sites only: an upper bound |
| PM2.5 | 12 km model grid | Modeled; cannot separate neighborhoods |
| Respiratory ED visits | Four-county Health Service Area | Measured, but regional and 80 days old |

## Before you record

- [ ] Make the interface public (`add-iam-policy-binding` on `clinic-broker-ui`).
- [ ] Do one live run on the deployed link and confirm it finishes.
- [ ] Run the notebook's validation section (section 12) and note one WARN worth a slide.
  Judges reward validation, and we loaded from the snapshot, so it has not been run yet.
- [ ] Time the script out loud once. Teams almost always run long.
- [ ] Merge the `rene` PR into `main`, so the repo judges see has the code.
- [ ] Upload to portal.angelhack.com/a4i-console: the repo link, the Skills project link,
  the deck and the video.
