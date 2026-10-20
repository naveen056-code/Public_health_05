"""BigQuery reads for the planning side of the system.

Nothing in this module reads race or ethnicity. The planner's only route to data is
through these functions, which is what makes "the planner cannot see race" a property
of the code rather than a sentence in a prompt.

Every number handed to an agent travels with the scale it was measured at, because the
eight tables sit at four different resolutions and none of them says so.
"""

from __future__ import annotations

import calendar
import datetime as dt
import math
from functools import lru_cache

from google.cloud import bigquery

from . import config

SCALES = {
    "pct_uninsured": "tract · modeled estimate (CDC PLACES, adults 18-64)",
    "pct_diabetes": "tract · modeled estimate (CDC PLACES)",
    "pct_high_bp": "tract · modeled estimate (CDC PLACES)",
    "pct_checkup": "tract · modeled estimate (CDC PLACES); low is bad",
    "pct_no_vehicle": "tract · survey estimate (CDC SVI / ACS)",
    "pct_limited_english": "tract · survey estimate (CDC SVI / ACS)",
    "km_to_safety_net": (
        "tract centre → federal safety-net site · straight line, county sites only, "
        "an upper bound (free and county clinics are not in any federal list)"
    ),
    "km_to_any_care": "tract centre → any federal care site · straight line, upper bound",
    "pm25": "12 km model grid reported at tract centres · cannot separate neighborhoods",
    "respiratory": (
        "Health Service Area (several counties) written onto a county key · "
        "cannot describe a neighborhood"
    ),
}

DEFAULT_WEIGHTS = {
    "uninsured": 0.30,
    "distance": 0.25,
    "no_vehicle": 0.20,
    "chronic": 0.15,
    "no_checkup": 0.10,
}

SAFETY_NET_KINDS = ("FQHC", "Health Center site")


@lru_cache(maxsize=1)
def _client() -> bigquery.Client:
    return bigquery.Client(project=config.PROJECT, location=config.BQ_LOCATION)


def _rows(sql: str, params: list | None = None) -> list[dict]:
    job = _client().query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params or []))
    return [dict(r) for r in job.result()]


def _r(x, nd=2):
    return None if x is None else round(float(x), nd)


# ---------------------------------------------------------------------------
# Ranking: what "needs the van" means
# ---------------------------------------------------------------------------
# Each input is percent-ranked against the other tracts in the county, so a weight is
# a statement about priorities rather than about units. Diabetes and blood pressure
# stand for chronic burden because they are what the van's glucometer and cuff screen
# for. Air quality and the respiratory trend are left out on purpose: one is a 12 km
# grid and the other a multi-county region, so neither can tell one tract from another.
_RANK_SQL = """
WITH b AS (
  SELECT b.geo_id, b.total_pop, b.pct_uninsured, b.pct_no_vehicle, b.pct_checkup,
         b.pct_diabetes, b.pct_high_bp, b.pct_limited_english, b.latitude, b.longitude,
         a.km_to_any_care, a.km_to_safety_net, a.extra_km_if_uninsured
  FROM {burden} b JOIN {access} a USING (geo_id)
  WHERE b.total_pop >= @min_population
    AND b.latitude IS NOT NULL AND a.km_to_safety_net IS NOT NULL
),
r AS (
  SELECT *,
    PERCENT_RANK() OVER (ORDER BY pct_uninsured)      AS r_uninsured,
    PERCENT_RANK() OVER (ORDER BY km_to_safety_net)   AS r_distance,
    PERCENT_RANK() OVER (ORDER BY pct_no_vehicle)     AS r_no_vehicle,
    (PERCENT_RANK() OVER (ORDER BY pct_diabetes)
       + PERCENT_RANK() OVER (ORDER BY pct_high_bp)) / 2 AS r_chronic,
    1 - PERCENT_RANK() OVER (ORDER BY pct_checkup)    AS r_no_checkup
  FROM b
)
SELECT *,
  (@w_uninsured * r_uninsured + @w_distance * r_distance + @w_no_vehicle * r_no_vehicle
   + @w_chronic * r_chronic + @w_no_checkup * r_no_checkup)
  / (@w_uninsured + @w_distance + @w_no_vehicle + @w_chronic + @w_no_checkup) AS need_score
FROM r
ORDER BY need_score DESC
"""


def ranked_tracts(weights: dict | None = None, min_population: int = 500) -> list[dict]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    params = [bigquery.ScalarQueryParameter(f"w_{k}", "FLOAT64", float(v)) for k, v in w.items()]
    params.append(bigquery.ScalarQueryParameter("min_population", "INT64", int(min_population)))
    sql = _RANK_SQL.format(burden=config.table("burden_tracts"), access=config.table("tract_access"))
    rows = _rows(sql, params)
    for i, r in enumerate(rows, start=1):
        r["need_rank"] = i
        r["tracts_ranked"] = len(rows)
    return rows


def tract_summary(r: dict) -> dict:
    """One tract as an agent should see it: each value next to its scale."""
    return {
        "geo_id": r["geo_id"],
        "need_rank": r["need_rank"],
        "need_rank_of": r["tracts_ranked"],
        "need_rank_note": f"of {r['tracts_ranked']} tracts with 500+ people",
        "need_score": _r(r["need_score"], 3),
        "population": int(r["total_pop"]),
        "pct_uninsured": {"value": _r(r["pct_uninsured"], 1), "scale": SCALES["pct_uninsured"]},
        "pct_no_vehicle": {"value": _r(r["pct_no_vehicle"], 1), "scale": SCALES["pct_no_vehicle"]},
        "km_to_safety_net": {"value": _r(r["km_to_safety_net"]), "scale": SCALES["km_to_safety_net"]},
        "km_to_any_care": {"value": _r(r["km_to_any_care"]), "scale": SCALES["km_to_any_care"]},
        "pct_diabetes": {"value": _r(r["pct_diabetes"], 1), "scale": SCALES["pct_diabetes"]},
        "pct_high_bp": {"value": _r(r["pct_high_bp"], 1), "scale": SCALES["pct_high_bp"]},
        "pct_checkup": {"value": _r(r["pct_checkup"], 1), "scale": SCALES["pct_checkup"]},
        "pct_limited_english": {
            "value": _r(r["pct_limited_english"], 1), "scale": SCALES["pct_limited_english"]},
    }


def _km(a: dict, b: dict) -> float:
    p = math.radians
    x = (math.sin(p(b["latitude"] - a["latitude"]) / 2) ** 2
         + math.cos(p(a["latitude"])) * math.cos(p(b["latitude"]))
         * math.sin(p(b["longitude"] - a["longitude"]) / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(x))


def select_stops(ranked: list[dict], *, stops: int = 4, min_spacing_km: float = 5.0,
                 min_km_to_safety_net: float = 3.0, exclude: list[str] | None = None,
                 include: list[str] | None = None) -> list[dict]:
    """Walk the ranking top-down, keeping a tract only if it is far enough from every
    stop already chosen. Without the spacing rule the top four are often neighbours,
    and four Saturdays in one neighbourhood is one Saturday's worth of reach."""
    exclude = set(exclude or [])
    by_id = {r["geo_id"]: r for r in ranked}
    chosen = [by_id[g] for g in (include or []) if g in by_id][:stops]
    for r in ranked:
        if len(chosen) >= stops:
            break
        if r["geo_id"] in exclude or r in chosen:
            continue
        if r["km_to_safety_net"] < min_km_to_safety_net:
            continue
        if all(_km(r, c) >= min_spacing_km for c in chosen):
            chosen.append(r)
    return chosen


def nearest_safety_net(geo_ids: list[str]) -> dict[str, dict]:
    """Where the van should send people for follow-up: the nearest site that will see
    somebody uninsured, with its weekly hours, since a site open eight hours a week and
    one open sixty are not the same supply."""
    sql = f"""
    WITH t AS (SELECT geo_id, ST_GEOGPOINT(longitude, latitude) pt FROM {config.table('burden_tracts')}
               WHERE geo_id IN UNNEST(@ids)),
         s AS (SELECT FACILITY_NM, CMS_PROVIDER_ADDRESS, CMS_PROVIDER_CITY, TOT_OPER_HR_PER_WEEK,
                      site_kind, ST_GEOGPOINT(longitude, latitude) pt
               FROM {config.table('care_sites')} WHERE site_kind IN UNNEST(@kinds))
    SELECT geo_id, ARRAY_AGG(STRUCT(FACILITY_NM AS name, CMS_PROVIDER_ADDRESS AS address,
             CMS_PROVIDER_CITY AS city, TOT_OPER_HR_PER_WEEK AS hours_per_week, site_kind,
             ST_DISTANCE(t.pt, s.pt) / 1000 AS km) ORDER BY ST_DISTANCE(t.pt, s.pt) LIMIT 1)[OFFSET(0)] site
    FROM t CROSS JOIN s GROUP BY geo_id
    """
    rows = _rows(sql, [bigquery.ArrayQueryParameter("ids", "STRING", geo_ids),
                       bigquery.ArrayQueryParameter("kinds", "STRING", list(SAFETY_NET_KINDS))])
    out = {}
    for r in rows:
        s = dict(r["site"])
        s["km"] = _r(s["km"])
        s["hours_per_week"] = _r(s["hours_per_week"], 0)
        s["scale"] = "facility point · federal sites only (HRSA / CMS)"
        out[r["geo_id"]] = s
    return out


def saturdays(month: str | None = None) -> list[str]:
    """Saturdays of `month` ('YYYY-MM'), defaulting to next calendar month."""
    if month:
        year, mon = (int(x) for x in month.split("-"))
    else:
        today = dt.date.today()
        year, mon = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    days = calendar.Calendar().itermonthdates(year, mon)
    return [d.isoformat() for d in days if d.month == mon and d.weekday() == calendar.SATURDAY]


# ---------------------------------------------------------------------------
# Evidence: the three independent lookups the pipeline runs in parallel
# ---------------------------------------------------------------------------

def need_evidence() -> dict:
    ranked = ranked_tracts()
    totals = _rows(f"""
      SELECT COUNT(*) tracts, SUM(total_pop) population,
             COUNTIF(extra_km_if_uninsured > 0) tracts_with_safety_net_gap,
             SUM(IF(km_to_safety_net > 5, total_pop, 0)) people_over_5km_from_safety_net,
             APPROX_QUANTILES(km_to_safety_net, 2)[OFFSET(1)] median_km_to_safety_net,
             MAX(km_to_safety_net) worst_km_to_safety_net
      FROM {config.table('tract_access')}""")[0]
    return {
        "county": config.COUNTY_NAME,
        "definition": (
            "need_score = county percent-rank of uninsured (0.30), km to a safety-net site "
            "(0.25), no-vehicle households (0.20), diabetes+high blood pressure (0.15), "
            "missing a routine checkup (0.10); tracts under 500 people excluded"),
        "county_totals": {k: (_r(v) if isinstance(v, float) else v) for k, v in totals.items()},
        "top_candidates": [tract_summary(r) for r in ranked[:12]],
    }


def context_evidence() -> dict:
    air = _rows(f"""
      SELECT APPROX_QUANTILES(mean_pm, 10)[OFFSET(1)] p10, APPROX_QUANTILES(mean_pm, 10)[OFFSET(9)] p90,
             MIN(mean_pm) lo, MAX(mean_pm) hi, MAX(days_over_35) max_days_over_35
      FROM {config.table('exposure_tracts')}""")[0]
    weeks = _rows(f"""
      SELECT CAST(week_end AS STRING) week_end, hsa, hsa_counties,
             percent_visits_covid covid, percent_visits_influenza flu, percent_visits_rsv rsv,
             ed_trends_covid, ed_trends_influenza, ed_trends_rsv
      FROM {config.table('disease_weekly')} ORDER BY week_end DESC LIMIT 6""")
    usable = _rows(f"""SELECT COUNTIF(percent_visits_covid IS NOT NULL) usable, COUNT(*) total
                      FROM {config.table('disease_weekly')}""")[0]
    shortage = _rows(f"""SELECT (SELECT COUNT(*) FROM {config.table('shortage_areas')}) areas,
                                (SELECT COUNT(*) FROM {config.table('shortage_facilities')}) facilities""")[0]
    return {
        "air_quality": {
            "p90_over_p10": _r(air["p90"] / air["p10"], 3) if air["p10"] else None,
            "min_mean_pm25": _r(air["lo"]), "max_mean_pm25": _r(air["hi"]),
            "max_days_over_35": air["max_days_over_35"],
            "scale": SCALES["pm25"],
            "use": "county-level context and bad-day warnings only; never used to rank tracts",
        },
        "respiratory_trend": {
            "region": weeks[0]["hsa"] if weeks else None,
            "region_counties": weeks[0]["hsa_counties"] if weeks else None,
            "usable_weeks": usable["usable"], "total_weeks": usable["total"],
            "latest_week_age_days": (
                (dt.date.today() - dt.date.fromisoformat(weeks[0]["week_end"][:10])).days
                if weeks else None),
            "latest_weeks": [{k: (_r(v) if isinstance(v, float) else v) for k, v in w.items()
                              if k not in ("hsa", "hsa_counties")} for w in weeks],
            "scale": SCALES["respiratory"],
        },
        "shortage_areas": {
            "live_designations": shortage["areas"],
            "note": ("0 means no live federal shortage-area designation (in Fulton all 99 are "
                     "'Proposed For Withdrawal'), not that there is no shortage. No signal is "
                     "not no problem." if shortage["areas"] == 0 else "live HRSA designations"),
            "shortage_facilities": shortage["facilities"],
            "facilities_note": "marks where care already IS; never a siting signal",
        },
    }


def capacity_evidence() -> dict:
    rows = _rows(f"""
      SELECT site_kind, COUNT(*) sites,
             APPROX_QUANTILES(TOT_OPER_HR_PER_WEEK, 2)[OFFSET(1)] median_hours,
             COUNTIF(TOT_OPER_HR_PER_WEEK < 20) under_20_hours
      FROM {config.table('care_sites')} GROUP BY site_kind ORDER BY sites DESC""")
    return {
        "care_sites_by_kind": [{k: (_r(v, 0) if isinstance(v, float) else v) for k, v in r.items()}
                               for r in rows],
        "safety_net_kinds": list(SAFETY_NET_KINDS),
        "scale": "facility points · federal sites only (HRSA / CMS); hours only on HRSA sites",
        "caveat": ("Hospitals are care but not safety-net care: a hospital is a bill. Distances "
                   "stop at the county line."),
    }
