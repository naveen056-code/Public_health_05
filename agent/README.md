# Clinic Broker: where the mobile clinic parks, and why

**Track: Siting.** Our agent helps **the outreach lead** in **Fulton County, GA** decide
**where the county's one mobile clinic parks on next month's four Saturdays**, and the
thing it knows that a spreadsheet does not is **which of its own numbers it can trust, at
what scale, and whether the plan lands fairly on the people it is meant to reach.**

Siting leads, and the other two tracks run behind it on the same plan, each as its own
agent: **Accountability** (an equity audit, plus a statement for a funder or program
director) and **Explanation** (a printable bilingual flyer and text messages for the
neighborhood). They are what make the siting plan honest.

**Live Feature Deployment:** [https://clinic-broker-ui-naveen-702160158477.us-east1.run.app/](https://clinic-broker-ui-naveen-702160158477.us-east1.run.app/)  
**Instant Demo (Saved Replay):** [https://clinic-broker-ui-naveen-702160158477.us-east1.run.app/#sample](https://clinic-broker-ui-naveen-702160158477.us-east1.run.app/#sample)  
**Base Deployment:** [https://clinic-broker-ui-702160158477.us-east1.run.app/](https://clinic-broker-ui-702160158477.us-east1.run.app/)  
**Local Test Link:** [http://localhost:8080](http://localhost:8080) (or [http://localhost:8080/#sample](http://localhost:8080/#sample))

Pick a month and press **Plan the month** (two to five minutes), or load `#sample` to replay a saved run instantly. The UI features a dynamic, zoomable Leaflet county map with animated route flow, an animated Doctor Van marker driving between stops with speech bubbles, live metric switching (Need Score, Uninsured %, No Vehicle %, Clinic Distance), Saturday detail cards, and full tabs for the equity audit, printable bilingual flyer, funder statement, and data limits. ADK's developer UI with the event graph is at `/dev-ui/`.

## What it produces: the Clinic Plan

1. **Where the van goes, and why.** Four dated Saturdays, each a named census tract with
   its population, need rank, the two or three numbers that put it there, and the nearest
   clinic that sees uninsured patients for follow-up care, with its weekly hours.
2. **What we could not tell you.** Every limit named with its scale: the air data is a 12 km
   grid, the respiratory data is a four-county region and 11+ weeks old, there are no live
   shortage areas, the clinic list is federal-only, and distances are straight-line.
3. **Who this plan lands on.** The equity audit: plan vs. high-need tracts vs. county, on
   race and ethnicity the planner never saw, plus age 65+, limited English, disability and
   no-vehicle households. The audit result is reported whether it passes or not.
4. **What we hand to the neighborhood.** A printable flyer, one page per Saturday with
   English above the fold and Spanish below; text messages in both languages; and a "why
   not us?" script for the closest neighborhood that did not get a Saturday. The explainer
   writes only the headline, invitation and message. The date, the free checks, the
   follow-up clinic, its address and hours are filled in by code, and the time and parking
   spot are left as blank lines for staff, so the model cannot get a fact wrong on paper.

Plus, for the **Accountability track**: an **accountability statement** for a funder or
program director: where the van goes and why, who the plan reaches (the audit's own
table), how it was checked and what the audit changed, what a plan cannot show yet, and
what to count on each Saturday (aggregate only) to prove the money went where the need was.
It states plainly that four Saturdays reach about 6.5% of the people in the highest-need
tracts.

## Architecture

```
clinic_plan (SequentialAgent)
├─ gather_evidence (ParallelAgent)        no model; fixed SQL
│   ├─ need_lookup      → state.evidence_need       tract
│   ├─ context_lookup   → state.evidence_context    12 km grid · multi-county region
│   └─ capacity_lookup  → state.evidence_capacity   facility points
├─ planner (LlmAgent)                     tools: plan_saturdays, rank_tracts
│     → state.plan, plan_stops, need_pool_geo_ids, plan_versions
├─ review_loop (LoopAgent, max 3 rounds; always ends on an audit)
│   ├─ auditor (LlmAgent)                 tool: BigQuery managed MCP (execute_sql_readonly)
│   │     reads plan_stops, plan, need_pool_geo_ids
│   │     → state.audit_report, audit_verdict, audit_table (captured from the MCP result)
│   │     PASS ends the loop
│   └─ revise_if_rejected → reviser (LlmAgent, same tools as planner)
│         reads audit_report, plan, plan_params → state.plan, plan_stops (new version)
├─ write_outputs (ParallelAgent)          both read only the final plan
│   ├─ explainer (LlmAgent, output_schema)    reads plan_stops, plan_runner_up → state.outreach
│   └─ accountability_writer (LlmAgent)       reads computed facts + audit_table → state.accountability
└─ clinic_plan_report                     no model; assembles the Clinic Plan and saves
                                          flyers.html + accountability_statement.md as artifacts
```

### Who can see what (this is the design)

| Agent | Can see | Cannot see |
|---|---|---|
| Planner / reviser | Our tools over the challenge tables (need, access, capacity) | Race or ethnicity: **no tool it holds can read them** |
| Auditor | The plan's tract IDs and text; Census race and ethnicity via BigQuery MCP | The planner's reasoning (`include_contents="none"`), so it cannot be talked into defending the plan |
| Explainer | The final stops and the runner-up | The analysis, the audit, the raw tables |
| Accountability writer | Facts computed in code, and the audit's own equity table | The raw tables; it is told to add no number the facts do not contain |

"The planner cannot see race" is enforced by the code, not by a sentence in a prompt: the
planner's only route to data is [`tools.py`](clinic_broker/tools.py) →
[`data.py`](clinic_broker/data.py), which never reads demographics. The Census join exists
only in [`audit.py`](clinic_broker/audit.py), and only the auditor holds the MCP tool.

### The four judge questions

1. **Delete any one agent and the answer gets worse.** Without the auditor, the
   uninsured-only plan below ships unchanged and under-reaches older adults. Without the
   explainer, the neighborhood gets a document written for a professional. Without the
   accountability writer, the funder gets an operational plan instead of an answer to
   "did the money go where the need was". Without the planner, nothing produces the stops.
2. **A state key written by one agent and read by another:** `plan_stops` is written by the
   planner's `plan_saturdays` tool and read by the auditor (to build its Census query), the
   explainer and the accountability writer. `audit_report` is written by the auditor and
   read by the reviser; `audit_table` is captured from the auditor's MCP call and read by
   the accountability writer.
3. **Agents whose instructions conflict:** the planner must *hedge, cite and label every
   number with its scale*; the explainer must be *warm, plain, sixth-grade, no statistics,
   no hedging*, in English and Spanish; the accountability writer must be *formal, third
   person, each figure once with its source, limits in their own section*. See
   [`prompts.py`](clinic_broker/prompts.py) and [`accountability.py`](clinic_broker/accountability.py).
4. **Where the system rejected its own first answer:** see the second run below.

## What "needs the van" means

Each tract (500+ people) is percent-ranked within the county on five measures and combined:

| Measure | Weight | Why |
|---|---:|---|
| Uninsured, adults 18-64 (PLACES `pct_uninsured`) | 0.30 | The van exists for people a clinic will not see for free |
| Straight-line km to a safety-net site (FQHC / HRSA health center) | 0.25 | Care you can actually use, not any care |
| Households with no vehicle (SVI) | 0.20 | A car makes 5 km nothing; no car makes it a day off work |
| Diabetes + high blood pressure (PLACES) | 0.15 | What the van's glucometer and cuff screen for |
| Adults without a routine checkup (PLACES) | 0.10 | Low is bad on this one |

Then: skip tracts already within 3 km of a safety-net site, and keep the four stops at
least 5 km apart so four Saturdays reach four areas. **Air quality and the respiratory
trend are deliberately not inputs:** in Fulton the cleanest and dirtiest tracts' PM2.5
differ by 4.7% (p90/p10) because it is a 12 km grid, and the respiratory figure covers
Clayton, DeKalb, Fulton and Gwinnett together.

## The equity audit, and what it found

The auditor compares the people living in the four stop tracts with the **need pool**
(the top quarter of tracts by need score), not with the county: a plan built on need
should not look like the county. It flags a group that is under-reached (under half its
need-pool share), and checks whether any over-concentration is explained by measured need
or is a proxy for something else. Race and ethnicity come from the 2016-2020 ACS
(`bigquery-public-data.census_bureau_acs.censustract_2020_5yr`, US Government work); the
challenge tables leave them out on purpose.

**Run 1: default weights → PASS.**

| | Plan | Need pool | County |
|---|---:|---:|---:|
| Black, non-Hispanic | 63.6% | 73.6% | 43.1% |
| White, non-Hispanic | 6.8% | 11.8% | 39.3% |
| Hispanic, any race | 25.4% | 9.5% | 7.2% |
| Asian, non-Hispanic | 0.6% | 1.9% | 7.3% |

The Hispanic over-concentration comes from one stop, tract 13121011430, and the auditor
found it explained by measured need: 24.9% uninsured and 13.5 km from a safety-net site.
With four stops, one tract moves a share by 20+ points, and the audit says so.

**Run 2: "rank only on the uninsured rate, that's what our funder cares about" → REVISE,
then PASS.** The auditor found the plan under-reached adults 65+ (**5.4%** of the plan
vs **12.7%** of the need pool). The cause is a defect the challenge warns about:
`pct_uninsured` covers adults 18-64 only, and Medicare covers almost everyone over 65, so
ranking on it alone pushes older neighborhoods down. The required fix was need-based
(restore chronic-disease and vehicle weights), never "add more of a group". The revised
plan opens with *"We changed what you asked for"*, saying what was asked, what changed, why,
and that the original is still available: overriding the user is the outreach lead's call
to see, not ours to hide.

The rule for disagreements: the reviser may change only need and access parameters. If an
equity finding cannot be fixed that way, it keeps the stops and reports an *open
disagreement with the audit* for the outreach lead to decide.

## Scale of every number

| Claim | Scale | Measured or modeled |
|---|---|---|
| Uninsured, diabetes, blood pressure, checkup | Census tract | **Modeled** (CDC PLACES small-area estimates) |
| No vehicle, limited English, age 65+ | Census tract | Survey estimate (CDC SVI / ACS) |
| Race and ethnicity (audit only) | Census tract | Survey estimate (ACS 2016-2020) |
| km to care | Tract centre → facility point | Computed; straight line, federal sites only: an **upper bound** |
| PM2.5 | **12 km model grid** wearing a tract ID | Modeled; cannot separate neighborhoods |
| Respiratory ED visits | **Multi-county Health Service Area** on a county key | Measured, but regional and 11+ weeks old |

## Limitations

- **Straight-line distance is not travel time.** No license-clean travel-time dataset exists.
- **Federal clinics only.** County and free clinics are in no national list, so every
  distance is an upper bound.
- **Distances stop at the county line.** A border tract may be closer to a clinic next door.
- **Modeled prevalence.** Two tracts a point apart may be the same tract; PLACES confidence
  intervals are not loaded yet.
- **Zero live shortage areas in Fulton.** All 99 HRSA designations are *Proposed For
  Withdrawal*. No signal is not no problem.
- **Run-to-run variation.** The stops come from deterministic SQL, but when the reviser
  re-weights, its choice of weights can differ between runs.
- **No parking spots or times.** The explainer writes `[parking spot]` and `[time]` for
  staff to fill in rather than invent them.

## Run it

```bash
# Setup environment & install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run automated tests
PYTHONPATH=agent pytest tests -v

# Run locally
gcloud auth application-default login            # if querying live BigQuery
cp agent/clinic_broker/.env.example agent/clinic_broker/.env   # set GOOGLE_CLOUD_PROJECT
PYTHONPATH=agent uvicorn agent.main:app --host 127.0.0.1 --port 8080
# Interface: http://127.0.0.1:8080 (or http://127.0.0.1:8080/#sample)
# ADK developer UI: http://127.0.0.1:8080/dev-ui/
```

`GOOGLE_CLOUD_LOCATION` must be `global`: Gemini 3.x returns "model not found" on regional
endpoints in the lab project. The `mcp` package must stay below 2.0 for ADK 2.7
(`google-adk[mcp]==2.7.0` pins it).

**Deploy** (from the repo root; builds [`agent/Dockerfile`](Dockerfile), which serves
[`main.py`](main.py)):

```bash
gcloud run deploy clinic-broker-ui --source agent --project=$PROJECT --region=us-east1 \
  --memory=1Gi --timeout=900 --max-instances=1 \
  --set-env-vars=GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_CLOUD_LOCATION=global
```

`GOOGLE_CLOUD_LOCATION=global` matters: Gemini 3.x is served only there in the lab
project. `--max-instances=1` because sessions and artifacts are kept in memory. The
original ADK-only deployment (`adk deploy cloud_run --with_ui`) is still running as the
`clinic-broker` service.

The interface lives in [`ui/`](ui/): plain HTML, CSS and JavaScript with no build step.
It talks to ADK's own API on the same server (`/run_sse` to stream each agent's events,
the session and artifact routes for the results) plus one route of ours, `/api/map`, for
the need scores and clinic points. Tract boundaries are the Census Bureau's 2020 TIGERweb
tracts (US Government work), saved in `ui/fulton_tracts_2020.geojson`; BigQuery's public
tract tables are 2010 boundaries and match only 108 of Fulton's 326 tracts.
`ui/sample_run.json` is a saved real run (the uninsured-only request), used by
**Replay a saved run**.

## Files

| File | What it holds |
|---|---|
| [`agent.py`](clinic_broker/agent.py) | The pipeline wiring and who-sees-what |
| [`data.py`](clinic_broker/data.py) | Ranking SQL, stop selection, evidence lookups, scale labels. No demographics |
| [`tools.py`](clinic_broker/tools.py) | Our function tools: `plan_saturdays`, `rank_tracts` |
| [`audit.py`](clinic_broker/audit.py) | BigQuery MCP toolset, the Census audit query, verdict handling |
| [`prompts.py`](clinic_broker/prompts.py) | Planner, reviser and explainer instructions |
| [`outreach.py`](clinic_broker/outreach.py) | The explainer's output schema and the printable bilingual flyer |
| [`accountability.py`](clinic_broker/accountability.py) | Computed facts, the audit-table capture, and the accountability writer's instruction |
| [`workflow.py`](clinic_broker/workflow.py) | Model-free agents: evidence lookups, conditional reviser, report and artifacts |
| [`../main.py`](main.py) | The web server: ADK's API, our interface at `/`, the developer UI at `/dev-ui/`, and `/api/map` |
| [`../ui/`](ui/) | The interface: `index.html`, `styles.css`, `app.js`, tract boundaries and the saved sample run |

---

# Challenge notes from the organizers

*Kept as shipped: the requirements, and the ADK API as the organizers verified it on
2026-08-10.*

We built the on-ramp: every federally recognized care site in your county with coordinates, the
census tracts around them with disease burden, insurance, vehicle access and mobility, the federal
shortage designations with the withdrawal trap already filtered out, the air at the only scale it
works, the current respiratory signal with its real resolution stated, both distances computed for
every tract, the licenses checked, and a validation suite that tells you plainly whether any of it
is wrong. We did not build the vehicle. The design decisions in your agent are what you are judged
on.

## What has to be true of what you build here

- **An ADK agent**, in Python.
- **Genuine multi-agent orchestration.** This is your required differentiator. More than one agent,
  passing state, with at least two whose instructions actually conflict. [What that means
  concretely](#what-multi-agent-actually-has-to-mean-here) is below, and the four questions judges
  look for are at the bottom of this file.
- **At least one tool you built yourself.** A Python function tool, or one you defined in MCP
  Toolbox—either counts. The obvious candidate wraps a tract query. The more valuable one holds the
  logic that is not a single query: deciding what "needs the van" means, weighing a modeled
  prevalence against a measured distance, turning a ranked list into a plan with a recommendation
  and a reason attached. Consuming only prebuilt generic tools and calling that your design does not
  count.
- **At least one Google-managed MCP server, consumed.** Do not author your own—use BigQuery's
  built-in server or the [MCP Toolbox for Databases](https://github.com/googleapis/mcp-toolbox).
- **Deployed to Google Cloud**—Agent Runtime or Cloud Run, your choice.

## What multi-agent actually has to mean here

One agent with several tools is enough when the job is: read the request, pick a tool, answer.
Several agents earn their keep when one of these is structurally true. On this challenge three of
them are, and the second is the strong one.

**1. Two of your jobs need contradictory instructions.** A clinical-safety reviewer whose whole
prompt is *hedge, cite, refuse if unsure* cannot share a system prompt with an outreach writer whose
prompt is *warm, plain language, sixth-grade reading level, Spanish and English*. Put both in one
agent and you get hedged flyers and chatty clinical notes. **This is the two-minute experiment worth
running before you commit to an architecture.**

**2. The equity audit is structurally a second agent.** You are forbidden from using race as a model
input and required to audit your output against it. That means your system must contain a component
that sees data the planner was denied. It also must not share the planner's context, because an
agent asked to produce a plan and critique it in the same breath will defend the plan. **The rule
you were given forces the architecture.** Say that out loud in your demo—it is the best sentence
available to you on this challenge.

**3. Your evidence gathering is embarrassingly parallel.** Burden, access and exposure are three
independent lookups over three tables. Run them concurrently and your wall clock is one hop instead
of three.

**What does not count:** three system prompts behind an `if intent ==`. No shared state, no
disagreement, no component that can overrule another. That is one agent with a switch statement, and
probe 2 below finds it in a single question.

## The API, verified in a lab project on 2026-08-10

Verified against `google-adk==2.7.0` on 2026-08-10. PyPI's current release is 2.11.0, and on
2026-10-12 every class named in this section still imported cleanly from it—imports, not behavior,
so run `pip show google-adk` and try the import below before you build on it. Pin the version you
verified—`pip install google-adk==2.7.0`—before you paste anything in this section; the `Workflow`
graph API is new and the class names here are specific to it.

**`SequentialAgent`, `ParallelAgent` and `LoopAgent` all still work, and all three are deprecated**
in favor of the graph `Workflow`:

```
DeprecationWarning: SequentialAgent is deprecated in favor of Workflow and will be
removed in a future version. Workflow cannot yet be used as an LlmAgent sub-agent.
```

Read that second sentence before you refactor. **Using the deprecated classes is a perfectly fine
choice today**—they work, and `Workflow` cannot yet be a sub-agent of an `LlmAgent`, which is a real
constraint on how you compose things.

The shape that works, and that we ran end to end in a project exactly like yours:

```python
from pydantic import BaseModel
from google.adk import Workflow, Event
from google.adk.workflow import node, START
from google.adk.agents import Context, LlmAgent

class PlanRequest(BaseModel):
    county: str

@node
async def gather_burden(ctx: Context):
    ...                                     # a plain function. No model call.
    return Event(message="burden gathered")

plan_graph = Workflow(
    name="clinic_plan",
    description="Plans mobile clinic stops for a county.",   # REQUIRED to use as a tool
    input_schema=PlanRequest,                                # ALSO REQUIRED
    timeout=120.0,                                           # SEE BELOW. NOT OPTIONAL.
    edges=[(START, gather_burden)],   # add your remaining edges here
)

root_agent = LlmAgent(name="coordinator", model="gemini-3.6-flash", tools=[plan_graph])
```

### Five things that will cost you time if you meet them by accident

**A graph cycle with no `timeout` runs forever.** `Workflow` has no iteration-cap field of any kind,
and `timeout` defaults to `None`. We built a deliberately infinite plan-audit loop and it ran until
an external backstop killed it. With `timeout=5.0` it raised `NodeTimeoutError` cleanly. **If your
graph contains a cycle, set `timeout`.** `LoopAgent` at least has `max_iterations`; a graph does
not. Plan-then-audit-then-revise is a cycle, and it is the architecture this challenge pushes you
toward, so this one is coming for you specifically.

**Both `description` and `input_schema` are required** to use a `Workflow` as a tool, in that order
of complaint. Without a description: *"must have a description to be wrapped as a tool."* With one
but no schema: *"NodeTool requires an explicit Pydantic input_schema."*

**A schema'd workflow takes a JSON string, not a dict.** `run_debug('{"county": "Fulton"}')` works.
A dict or a model instance gets iterated into its keys and fails validation, because the runner is
typed for `str | list[str]`.

**Parallel branches share one state dict and will clobber each other.** The isolation is on
conversation history, not on state. Two branches both writing `output_key="shared"` leave one value
and no error. **Every parallel branch needs a distinct `output_key`.** This is the single most
likely way to lose an hour today, because it fails silently and the symptom is "the agent ignored
one of my lookups."

**A missing `{key}` in an instruction is a hard crash**, not a silent blank:
`KeyError: 'Context variable not found'`. Use `{key?}` if you want it optional. This is good news—it
means a typo surfaces immediately—but it also means you must run every agent once after wiring it.

### How to see it working, which is most of debugging

```python
from google.adk.runners import InMemoryRunner   # confirm the path against your pinned version
from google.adk.plugins import LoggingPlugin
runner = InMemoryRunner(agent=root_agent, plugins=[LoggingPlugin()])
await runner.run_debug("Plan next month's clinic stops.", verbose=True)
```

One line, and you get every agent transition, every model request, every tool call, and **token
usage per call**—which is how you find out whether your six-agent loop is affordable before you run
it fifty times.

In `adk web`, the **State** tab plus the event graph lets you click an event and see which node
produced it. On a multi-agent challenge that is not a convenience, it is the only view of the thing
you are being judged on. When the deck says how you debugged it, "we watched the event graph" is a
better answer than "we read the final output."

Two environment notes. In a notebook use a bare `await`, because `asyncio.run()` raises inside a
cell. And `adk web` defaults to port 8000 on 127.0.0.1, so in Cloud Shell run
`adk web --host 0.0.0.0 --port 8080` and use Web Preview.

### One constraint that has evaporated

On Gemini 2.5 and older, a built-in tool could not share an agent with a function tool of your own,
which forced a sub-agent wrapper. **On Gemini 3.x that restriction is gone.**

Do not cite it as your reason for going multi-agent. It is the most commonly repeated
already-fixed limitation in ADK, several judges know it, and using it as your architecture
justification signals that you inherited a pattern rather than chose one.

## The thing worth remembering while you build

**Your tables are at four different resolutions and not one of them says so.**

A census tract. A 12 km modeling grid wearing an eleven-digit tract ID. A facility point. A
multi-county Health Service Area written onto a county key. Every one of them is dressed up with an
identifier that suggests more precision than it has, no query fails, and every ranking you build
looks perfectly reasonable.

An agent that says *"respiratory illness is rising in this neighborhood"* from a four-county number
has produced something specific, plausible and false about people's health. An agent that says
*"I can tell you what respiratory visits are doing across the four-county area that includes this
one; I cannot tell you anything about this neighborhood, and neither can anything else available
publicly"* is more useful, more honest, and will score better.

That is the same shape as the trap in section 2 of the notebook, and it is the shape of the whole
challenge.

## The four questions judges look for

They are printed in the README too, so you have had them all day. Answer them in the deck or the
pitch video; nobody will ask them at a keyboard.

1. **Delete any one agent. Does the answer get worse?** If not, that agent was decoration. The
   strongest version of this answer is a before and after you can show.
2. **Show me a key in `session.state` written by one agent and read by another.** If there isn't
   one, you have a single agent and some function calls, however the diagram is drawn.
3. **Show me two agents whose instructions genuinely conflict.** Near-identical prompts are one
   agent wearing hats.
4. **Show me the point where your system rejected its own first answer.** This is the one that
   separates a good team from a winning one.

See the README for the nine data defects and the county-by-county warnings, and section 13 of the
notebook for the same API notes in context.
