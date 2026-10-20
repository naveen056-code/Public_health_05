"""The auditor's side of the wall.

The planner was forbidden race as an input. The auditor is required to check the plan
against it, so it gets a tool the planner does not have: BigQuery's Google-managed MCP
server, restricted to read-only SQL. The demographic query is built here, from the tract
IDs the planner saved to state, and nowhere in the planner's code.
"""

from __future__ import annotations

import json
import re
import threading

import google.auth
try:
    from google.adk.agents.callback_context import CallbackContext
    from google.adk.agents.readonly_context import ReadonlyContext
    from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
    from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
except ImportError:
    CallbackContext = None  # type: ignore
    ReadonlyContext = None  # type: ignore
    StreamableHTTPConnectionParams = None  # type: ignore
    McpToolset = None  # type: ignore
from google.auth.transport.requests import Request

from . import config
from .data import SCALES

_creds = None
_creds_lock = threading.Lock()


def _auth_headers(_ctx: ReadonlyContext | None = None) -> dict[str, str]:
    global _creds
    with _creds_lock:
        if _creds is None:
            _creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        if not _creds.valid:
            _creds.refresh(Request())
        return {"Authorization": f"Bearer {_creds.token}", "x-goog-user-project": config.PROJECT}


def bigquery_mcp() -> McpToolset:
    return McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=config.BIGQUERY_MCP_URL, timeout=30.0),
        tool_filter=["execute_sql_readonly"],
        header_provider=_auth_headers,
    )


def _ids_sql(ids: list[str]) -> str:
    # Tract IDs come from our own BigQuery tables, but they are interpolated into SQL,
    # so refuse anything that is not an eleven-digit tract code.
    clean = [i for i in ids if re.fullmatch(r"\d{11}", str(i))]
    return ", ".join(f"'{i}'" for i in clean) or "''"


def audit_sql(plan_ids: list[str], pool_ids: list[str]) -> str:
    """Plan vs. the high-need pool vs. the whole county, on the demographics the planner
    never saw (Census race and ethnicity) and on four it could see but did not rank on."""
    return f"""
WITH acs AS (
  SELECT geo_id, total_pop, black_pop, white_pop, hispanic_pop, asian_pop
  FROM `{config.ACS_TABLE}` WHERE STARTS_WITH(geo_id, '{config.COUNTY_FIPS}')
),
b AS (
  SELECT geo_id, total_pop AS places_pop, pct_age_65_plus, pct_limited_english,
         pct_any_disability, pct_no_vehicle
  FROM {config.table('burden_tracts')}
),
grp AS (
  SELECT 'plan' AS grp, geo_id FROM UNNEST([{_ids_sql(plan_ids)}]) AS geo_id
  UNION ALL SELECT 'need_pool', geo_id FROM UNNEST([{_ids_sql(pool_ids)}]) AS geo_id
  UNION ALL SELECT 'county', geo_id FROM b
)
SELECT grp, COUNT(*) AS tracts, CAST(SUM(acs.total_pop) AS INT64) AS population,
  ROUND(100 * SAFE_DIVIDE(SUM(black_pop), SUM(acs.total_pop)), 1)    AS pct_black_non_hispanic,
  ROUND(100 * SAFE_DIVIDE(SUM(white_pop), SUM(acs.total_pop)), 1)    AS pct_white_non_hispanic,
  ROUND(100 * SAFE_DIVIDE(SUM(hispanic_pop), SUM(acs.total_pop)), 1) AS pct_hispanic_any_race,
  ROUND(100 * SAFE_DIVIDE(SUM(asian_pop), SUM(acs.total_pop)), 1)    AS pct_asian_non_hispanic,
  ROUND(SAFE_DIVIDE(SUM(places_pop * pct_age_65_plus), SUM(places_pop)), 1)     AS pct_age_65_plus,
  ROUND(SAFE_DIVIDE(SUM(places_pop * pct_limited_english), SUM(places_pop)), 1) AS pct_limited_english,
  ROUND(SAFE_DIVIDE(SUM(places_pop * pct_any_disability), SUM(places_pop)), 1)  AS pct_any_disability,
  ROUND(SAFE_DIVIDE(SUM(places_pop * pct_no_vehicle), SUM(places_pop)), 1)      AS pct_no_vehicle
FROM grp JOIN acs USING (geo_id) JOIN b USING (geo_id)
GROUP BY grp ORDER BY grp
""".strip()


AUDITOR_TEMPLATE = """\
You are the independent equity and evidence auditor for a county mobile-clinic plan in
{county}. You did not write the plan and you have no stake in it. Your job is to find what
is wrong with it. You are skeptical, precise and terse. You cite numbers. You never soften
a finding to be polite, and you never invent a problem to look busy.

You see data the planner was forbidden to use: Census race and ethnicity by tract. You
use it only to check the plan's outcome. You never recommend choosing a tract because of
its racial or ethnic makeup.

## The plan you are auditing

Stops (tract IDs and the planner's own numbers):
{stops}

The planner's written plan:
<plan>
{plan}
</plan>

## Step 1: run the equity query

Call execute_sql_readonly with projectId "{project}" and exactly this query:

```sql
{sql}
```

It returns three rows: `plan` (people living in the stop tracts), `need_pool` (the top
quarter of the county's tracts by need score, which is the population the plan is meant
to reach) and `county`. Census figures are 2016-2020 ACS survey estimates at tract level.

## Step 2: judge equity

The question is not "does the plan look like the county". A plan built on need should
not. The question is: **did the plan land where people cannot reach care, or did the
model find a proxy for something else?**

- Compare `plan` with `need_pool`, not with `county`.
- A group is UNDER-REACHED if it is at least 10% of the need pool and its share of the
  plan is less than half its share of the need pool.
- A group is OVER-CONCENTRATED if its share of the plan is more than double its
  need-pool share. That is not wrong by itself. Check whether measured need explains it:
  look at the stop tracts' uninsured, distance and no-vehicle numbers above. If need
  explains it, say so and move on. If it does not, that is a proxy and it is a finding.
- Four stops is a small sample. One tract can move a share by 20 points. Say so when
  that is what happened rather than calling it a pattern.

## Step 3: judge the evidence

Read every claim in the planner's written plan. These are the scales the data has:
{scales}

Flag, quoting the sentence:
- any claim about air quality or respiratory illness that is stated or implied at
  neighborhood or tract level (air is a 12 km grid; respiratory data is a multi-county
  region);
- any modeled PLACES estimate presented as a count or as measured;
- any distance presented as travel time or as "the nearest care available" rather than
  the nearest federal site, straight line;
- any number that does not match the stop data above;
- any stop that lacks a stated reason or a referral site.

## Output

Write exactly this structure:

VERDICT: PASS or VERDICT: REVISE

EQUITY
- one line per group: plan % vs need pool % vs county %, and your reading of it

EVIDENCE
- one line per problem, quoting the sentence, or "No scale or number problems found."

REQUIRED CHANGES
- numbered, concrete, and expressed in terms of places and measured need (tracts,
  uninsured, distance, vehicles, spacing, wording). Never "add more <group>".
- or "None."

Choose REVISE if there is any EVIDENCE problem, or any UNDER-REACHED group, or any
OVER-CONCENTRATION that need does not explain. Otherwise PASS.
{history}"""


def auditor_instruction(ctx: ReadonlyContext) -> str:
    state = ctx.state
    stops = state.get("plan_stops", [])
    history = ""
    if state.get("audit_history"):
        last = state["audit_history"][-1]
        history = (
            "\n## Your previous audit of an earlier version\n"
            f"{last['report']}\n\nCheck whether each required change was made. Do not repeat "
            "findings that have been fixed; do not drop findings that have not.\n")
    return AUDITOR_TEMPLATE.format(
        county=config.COUNTY_NAME,
        stops=json.dumps(stops, indent=1, default=str),
        plan=state.get("plan", "(no written plan)"),
        project=config.PROJECT,
        sql=audit_sql([s["geo_id"] for s in stops], state.get("need_pool_geo_ids", [])),
        scales="\n".join(f"- {k}: {v}" for k, v in SCALES.items()),
        history=history,
    )


def record_verdict(callback_context: CallbackContext):
    """Turns the auditor's text into state the rest of the system can act on, and ends
    the review loop on a PASS."""
    state = callback_context.state
    report = state.get("audit_report", "") or ""
    m = re.search(r"VERDICT:\s*\**\s*(PASS|REVISE)", report, re.IGNORECASE)
    verdict = m.group(1).upper() if m else "REVISE"
    state["audit_verdict"] = verdict
    state["audit_history"] = state.get("audit_history", []) + [{
        "round": len(state.get("audit_history", [])) + 1,
        "plan_version": len(state.get("plan_versions", [])),
        "verdict": verdict,
        "report": report,
    }]
    if verdict == "PASS":
        callback_context.actions.escalate = True
    return None
