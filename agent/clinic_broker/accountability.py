"""The accountability statement: the plan written up for a funder or program director.

Its reader asks one question: did the money go where the need was? So it is built from
facts the code computes (who lives in the stop tracts, how far they are from care, what
the audit measured and what it changed), never from figures the model retypes."""

from __future__ import annotations

import json
import statistics

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools import BaseTool, ToolContext

from . import config


def _rows_from_mcp(response) -> list[dict] | None:
    """BigQuery MCP returns a jobs.query-shaped payload: a schema and rows of {f: [{v}]}."""
    payload = response.get("structuredContent") if isinstance(response, dict) else None
    if not payload and isinstance(response, dict):
        for part in response.get("content") or []:
            if isinstance(part, dict) and part.get("type") == "text":
                try:
                    payload = json.loads(part["text"])
                    break
                except (ValueError, KeyError):
                    continue
    if not payload or "schema" not in payload:
        return None
    names = [f["name"] for f in payload["schema"]["fields"]]
    return [dict(zip(names, (c.get("v") for c in r["f"]))) for r in payload.get("rows", [])]


def capture_audit_table(tool: BaseTool, args: dict, tool_context: ToolContext, tool_response):
    """Keeps the auditor's equity query result in state as a table, so the accountability
    statement reports the numbers the audit actually measured."""
    if tool.name != "execute_sql_readonly":
        return None
    rows = _rows_from_mcp(tool_response)
    if rows and rows[0].keys() >= {"grp", "pct_black_non_hispanic"}:
        tool_context.state["audit_table"] = rows
    return None


def _required_changes(report: str) -> str:
    """The REQUIRED CHANGES section of one audit report: the reason a version was rejected."""
    _, _, tail = (report or "").partition("REQUIRED CHANGES")
    return tail.strip() or "None."


def _facts(state: dict) -> dict:
    stops = state.get("plan_stops", [])
    totals = (state.get("evidence_need") or {}).get("county_totals", {})
    km = [s["km_to_safety_net"]["value"] for s in stops]
    population = sum(s["population"] for s in stops)
    audits = state.get("audit_history", [])
    versions = state.get("plan_versions", [])
    table = state.get("audit_table") or []
    by_group = {r.get("grp"): r for r in table}
    pool_pop = float(by_group.get("need_pool", {}).get("population") or 0)
    plan_pop = float(by_group.get("plan", {}).get("population") or 0)
    return {
        "county": config.COUNTY_NAME,
        "month": (state.get("plan_params") or {}).get("month"),
        "stops": [{
            "saturday": s["saturday"], "tract": s["geo_id"], "population": s["population"],
            "need_rank": f"{s['need_rank']} {s['need_rank_note']}",
            "pct_uninsured_18_64": s["pct_uninsured"]["value"],
            "pct_no_vehicle": s["pct_no_vehicle"]["value"],
            "km_to_safety_net": s["km_to_safety_net"]["value"],
            "refer_to": (s.get("refer_to") or {}).get("display_name"),
        } for s in stops],
        "people_living_in_stop_tracts": population,
        "share_of_county_population_pct": (
            round(100 * population / totals["population"], 1) if totals.get("population") else None),
        # Four Saturdays reach a small slice of the people the plan is aimed at. The
        # statement must say how small, not imply the program covers the need.
        # Both from the same Census table, so the ratio does not mix two population sources.
        "stop_tracts_population_census": int(plan_pop) if plan_pop else None,
        "stop_tracts_share_of_need_pool_population_pct": (
            round(100 * plan_pop / pool_pop, 1) if pool_pop else None),
        "need_pool_population": int(pool_pop) if pool_pop else None,
        "need_pool_tracts": by_group.get("need_pool", {}).get("tracts"),
        "median_km_to_safety_net_stops": round(statistics.median(km), 2) if km else None,
        "median_km_to_safety_net_county": totals.get("median_km_to_safety_net"),
        "people_in_county_over_5km_from_safety_net": totals.get("people_over_5km_from_safety_net"),
        "need_definition": (state.get("evidence_need") or {}).get("definition"),
        "parameters_used": state.get("plan_params"),
        "plan_versions": [{"version": v["version"], "tracts": v["geo_ids"],
                           "weights": v["params"]["weights"]} for v in versions],
        "audit_rounds": [{"round": a["round"], "plan_version": a["plan_version"],
                          "verdict": a["verdict"],
                          "required_changes": _required_changes(a["report"])} for a in audits],
        "final_audit_verdict": state.get("audit_verdict"),
        "equity_table_from_audit": state.get("audit_table"),
        "final_audit_report": audits[-1]["report"] if audits else None,
    }


TEMPLATE = """\
You write the accountability statement for {county}'s mobile clinic plan. Your reader is
a program director or a funder deciding whether this program puts its money where the
need is. They read it once, carefully, and may quote it in a grant report.

Write formally, in the third person, like a grant report. Lead with what the plan does.
State each figure once, with its source, named only as one of: CDC PLACES 2025 (uninsured,
chronic disease, checkups), CDC/ATSDR SVI 2022 (vehicles, age, disability, limited
English), Census ACS 2016-2020 (race and ethnicity), HRSA and CMS facility files (clinics,
distances), or "the plan's equity audit". Never invent a source name. No adjectives that are not evidence, no
marketing language and no apologies: a limitation is stated plainly in its own section,
not spread through every sentence. Never round a number the facts give you, never add a
number they do not, and never describe any individual's health.

This is a plan, not a result: the Saturdays have not happened. Say so, and say what would
have to be counted afterwards to show the money went where the need was.

## The facts (computed by the system; use only these)

```json
{facts}
```

`equity_table_from_audit` has one row per group: `plan` (people living in the four stop
tracts), `need_pool` (the top quarter of the county's tracts by need score) and `county`.
Race and ethnicity there are 2016-2020 ACS survey estimates; they were used only to check
the plan, never to choose it.

## Output (markdown, nothing else)

### Accountability statement: {county}, <month>
A three-sentence summary: where the van goes, why those places, and what the equity audit
concluded.

### Where the van goes and why
A table: Saturday, tract, people living there, need rank, uninsured adults 18-64 (%), no
vehicle (%), km to the nearest safety-net clinic, follow-up clinic. Then one sentence on
how need was defined.

### Who the plan reaches
First one sentence of scale, from the facts: the stop tracts are home to
stop_tracts_population_census people, which is stop_tracts_share_of_need_pool_population_pct
percent of the need_pool_population people in the need_pool_tracts highest-need tracts.
Four Saturdays reach a small part of the need; say so plainly, and never describe the plan
as covering, reaching or serving most of the need.

Then a table from equity_table_from_audit with only percentage rows: each group's share in
the plan, the need pool and the county, including age 65+, limited English, disability and
no vehicle. Do not put tract counts or population in that table. Then two or three
sentences on what it shows, including what the auditor concluded and why. If the table is
missing, say the audit table was not captured and report the auditor's verdict only.

### How the plan was checked
The audit rounds, each verdict, and what changed between plan versions and why. The reason
a version was rejected is its round's required_changes; state that reason, not another. If the
final verdict is REVISE, say plainly that the auditor still objects and that the outreach
lead must decide.

### What this plan cannot show yet
Bullets: that it is a plan, not a result; that prevalence and uninsured rates are modeled
tract estimates, not counts; that distances are straight-line to federal sites only, so
they are upper bounds; and that the people served on the day may not live in the tract.

### What to count on each Saturday
Bullets: aggregate counts only, never names or anything that identifies a person: visits;
how many people had no insurance; how many had no regular source of care; the area people
came from (neighborhood or ZIP, not address); follow-up referrals made to the named clinic.
"""


def instruction(ctx: ReadonlyContext) -> str:
    return TEMPLATE.format(county=config.COUNTY_NAME,
                           facts=json.dumps(_facts(dict(ctx.state)), indent=1, default=str))
