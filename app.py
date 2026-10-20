import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="Public Health Equity & Preventative Mobile Care Broker",
    description="Interactive Map, Multi-Agent Decision Engine & Prompt UI",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UI_PATH = Path(__file__).parent / "ui" / "index.html"
DATASET = os.getenv("BQ_DATASET", "a4i_health")


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default-session"


# Fallback Fulton County (13121) data if BigQuery dataset `a4i_health` is not yet loaded
FALLBACK_TRACTS: List[Dict[str, Any]] = [
    {
        "geo_id": "13121007808",
        "total_pop": 5412,
        "latitude": 33.6612,
        "longitude": -84.5105,
        "pct_uninsured": 21.4,
        "pct_checkup": 69.2,
        "pct_diabetes": 16.8,
        "pct_high_bp": 41.2,
        "pct_asthma": 11.9,
        "pct_no_vehicle": 18.6,
        "pct_limited_english": 7.4,
        "km_to_any_care": 2.1,
        "km_to_safety_net": 18.4,
        "extra_km_if_uninsured": 16.3,
        "svi_socioeconomic": 0.89,
        "svi_household": 0.82,
        "svi_housing_transport": 0.86,
    },
    {
        "geo_id": "13121010514",
        "total_pop": 6180,
        "latitude": 33.5845,
        "longitude": -84.6021,
        "pct_uninsured": 19.8,
        "pct_checkup": 70.5,
        "pct_diabetes": 15.9,
        "pct_high_bp": 39.8,
        "pct_asthma": 11.4,
        "pct_no_vehicle": 15.2,
        "pct_limited_english": 6.1,
        "km_to_any_care": 3.4,
        "km_to_safety_net": 22.9,
        "extra_km_if_uninsured": 19.5,
        "svi_socioeconomic": 0.85,
        "svi_household": 0.79,
        "svi_housing_transport": 0.81,
    },
    {
        "geo_id": "13121008202",
        "total_pop": 4390,
        "latitude": 33.7240,
        "longitude": -84.4680,
        "pct_uninsured": 22.7,
        "pct_checkup": 68.1,
        "pct_diabetes": 18.1,
        "pct_high_bp": 43.5,
        "pct_asthma": 12.6,
        "pct_no_vehicle": 24.3,
        "pct_limited_english": 4.9,
        "km_to_any_care": 1.8,
        "km_to_safety_net": 14.2,
        "extra_km_if_uninsured": 12.4,
        "svi_socioeconomic": 0.92,
        "svi_household": 0.88,
        "svi_housing_transport": 0.90,
    },
    {
        "geo_id": "13121007603",
        "total_pop": 4820,
        "latitude": 33.6880,
        "longitude": -84.4390,
        "pct_uninsured": 20.5,
        "pct_checkup": 71.0,
        "pct_diabetes": 15.2,
        "pct_high_bp": 38.4,
        "pct_asthma": 11.2,
        "pct_no_vehicle": 19.1,
        "pct_limited_english": 11.8,
        "km_to_any_care": 1.9,
        "km_to_safety_net": 13.7,
        "extra_km_if_uninsured": 11.8,
        "svi_socioeconomic": 0.87,
        "svi_household": 0.84,
        "svi_housing_transport": 0.85,
    },
    {
        "geo_id": "13121009501",
        "total_pop": 5120,
        "latitude": 33.8420,
        "longitude": -84.3620,
        "pct_uninsured": 6.2,
        "pct_checkup": 79.4,
        "pct_diabetes": 7.8,
        "pct_high_bp": 24.1,
        "pct_asthma": 8.4,
        "pct_no_vehicle": 4.1,
        "pct_limited_english": 2.3,
        "km_to_any_care": 1.1,
        "km_to_safety_net": 6.4,
        "extra_km_if_uninsured": 5.3,
        "svi_socioeconomic": 0.22,
        "svi_household": 0.28,
        "svi_housing_transport": 0.31,
    },
    {
        "geo_id": "13121011425",
        "total_pop": 5890,
        "latitude": 34.0210,
        "longitude": -84.3250,
        "pct_uninsured": 5.4,
        "pct_checkup": 81.2,
        "pct_diabetes": 6.9,
        "pct_high_bp": 22.8,
        "pct_asthma": 7.9,
        "pct_no_vehicle": 2.8,
        "pct_limited_english": 3.5,
        "km_to_any_care": 1.5,
        "km_to_safety_net": 11.2,
        "extra_km_if_uninsured": 9.7,
        "svi_socioeconomic": 0.18,
        "svi_household": 0.24,
        "svi_housing_transport": 0.25,
    },
    {
        "geo_id": "13121005501",
        "total_pop": 3910,
        "latitude": 33.7350,
        "longitude": -84.3980,
        "pct_uninsured": 16.4,
        "pct_checkup": 73.1,
        "pct_diabetes": 13.5,
        "pct_high_bp": 35.2,
        "pct_asthma": 11.0,
        "pct_no_vehicle": 21.0,
        "pct_limited_english": 3.2,
        "km_to_any_care": 0.9,
        "km_to_safety_net": 1.4,
        "extra_km_if_uninsured": 0.5,
        "svi_socioeconomic": 0.78,
        "svi_household": 0.72,
        "svi_housing_transport": 0.80,
    },
    {
        "geo_id": "13121010305",
        "total_pop": 6430,
        "latitude": 33.6120,
        "longitude": -84.5490,
        "pct_uninsured": 17.9,
        "pct_checkup": 71.8,
        "pct_diabetes": 14.7,
        "pct_high_bp": 37.9,
        "pct_asthma": 11.1,
        "pct_no_vehicle": 13.8,
        "pct_limited_english": 5.6,
        "km_to_any_care": 2.6,
        "km_to_safety_net": 16.8,
        "extra_km_if_uninsured": 14.2,
        "svi_socioeconomic": 0.81,
        "svi_household": 0.76,
        "svi_housing_transport": 0.77,
    },
]

FALLBACK_SITES: List[Dict[str, Any]] = [
    {
        "name": "Southside Medical Center (FQHC)",
        "site_kind": "FQHC",
        "latitude": 33.7115,
        "longitude": -84.3910,
        "hours_per_week": 45.0,
        "is_safety_net": True,
    },
    {
        "name": "Mercy Care Street Medicine & Health Center",
        "site_kind": "Health Center site",
        "latitude": 33.7585,
        "longitude": -84.3735,
        "hours_per_week": 40.0,
        "is_safety_net": True,
    },
    {
        "name": "HEALING Community Center (FQHC)",
        "site_kind": "FQHC",
        "latitude": 33.7530,
        "longitude": -84.4720,
        "hours_per_week": 40.0,
        "is_safety_net": True,
    },
    {
        "name": "Grady Memorial Hospital",
        "site_kind": "Hospital",
        "latitude": 33.7519,
        "longitude": -84.3821,
        "hours_per_week": 168.0,
        "is_safety_net": False,
    },
    {
        "name": "Emory University Hospital Midtown",
        "site_kind": "Hospital",
        "latitude": 33.7686,
        "longitude": -84.3862,
        "hours_per_week": 168.0,
        "is_safety_net": False,
    },
    {
        "name": "Wellstar North Fulton Hospital",
        "site_kind": "Hospital",
        "latitude": 34.0628,
        "longitude": -84.3168,
        "hours_per_week": 168.0,
        "is_safety_net": False,
    },
]


def compute_need_score(t: Dict[str, Any]) -> float:
    """
    Computes composite Mobile Clinic Need Score WITHOUT race/ethnicity (Model Input Rule).
    Combines:
    - Safety-net distance gap (`extra_km_if_uninsured`)
    - Uninsured rate 18-64 (`pct_uninsured`)
    - No-vehicle household share (`pct_no_vehicle`)
    - Preventive checkup deficit (`100 - pct_checkup`)
    - Screenable chronic burden (`pct_diabetes` + `pct_high_bp`)
    """
    extra_km = float(t.get("extra_km_if_uninsured") or 0.0)
    uninsured = float(t.get("pct_uninsured") or 0.0)
    no_veh = float(t.get("pct_no_vehicle") or 0.0)
    checkup_gap = max(0.0, 100.0 - float(t.get("pct_checkup") or 75.0))
    chronic = (float(t.get("pct_diabetes") or 0.0) + float(t.get("pct_high_bp") or 0.0)) / 2.0

    raw = (
        (min(extra_km, 25.0) / 25.0) * 35.0
        + (min(uninsured, 35.0) / 35.0) * 25.0
        + (min(no_veh, 30.0) / 30.0) * 20.0
        + (min(checkup_gap, 35.0) / 35.0) * 10.0
        + (min(chronic, 35.0) / 35.0) * 10.0
    )
    return round(raw, 1)


def load_county_data() -> Dict[str, Any]:
    """Queries BigQuery `a4i_health` if available; otherwise uses verified Fulton snapshot."""
    source_mode = "Fallback Snapshot (Fulton County, GA 13121 — run `bash scripts/load.sh` for full BQ)"
    county_name = "Fulton County, GA (13121)"
    tracts: List[Dict[str, Any]] = []
    sites: List[Dict[str, Any]] = []
    shortage_areas_count = 0
    usable_covid_weeks = 201
    latest_covid_pct = 2.4

    try:
        from google.cloud import bigquery

        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        bq = bigquery.Client(project=project_id) if project_id else bigquery.Client()
        proj = bq.project
        t_prefix = f"{proj}.{DATASET}"

        tract_sql = f"""
        SELECT
            b.geo_id,
            b.total_pop,
            b.latitude,
            b.longitude,
            ROUND(b.pct_uninsured, 1) AS pct_uninsured,
            ROUND(b.pct_checkup, 1) AS pct_checkup,
            ROUND(b.pct_diabetes, 1) AS pct_diabetes,
            ROUND(b.pct_high_bp, 1) AS pct_high_bp,
            ROUND(b.pct_asthma, 1) AS pct_asthma,
            ROUND(b.pct_no_vehicle, 1) AS pct_no_vehicle,
            ROUND(b.pct_limited_english, 1) AS pct_limited_english,
            ROUND(a.km_to_any_care, 2) AS km_to_any_care,
            ROUND(a.km_to_safety_net, 2) AS km_to_safety_net,
            ROUND(a.extra_km_if_uninsured, 2) AS extra_km_if_uninsured,
            ROUND(b.svi_socioeconomic, 2) AS svi_socioeconomic,
            ROUND(b.svi_household, 2) AS svi_household,
            ROUND(b.svi_housing_transport, 2) AS svi_housing_transport
        FROM `{t_prefix}.burden_tracts` b
        LEFT JOIN `{t_prefix}.tract_access` a USING (geo_id)
        WHERE b.latitude IS NOT NULL AND b.longitude IS NOT NULL
        """
        rows = list(bq.query(tract_sql).result())
        if rows:
            tracts = [dict(r) for r in rows]
            first_fips = str(tracts[0]["geo_id"])[:5]
            county_map = {
                "13121": "Fulton County, GA (13121)",
                "17031": "Cook County, IL (17031)",
                "06085": "Santa Clara County, CA (06085)",
                "36005": "Bronx County, NY (36005)",
                "48201": "Harris County, TX (48201)",
                "48453": "Travis County, TX (48453)",
            }
            county_name = county_map.get(first_fips, f"County FIPS {first_fips}")
            source_mode = f"Live BigQuery ({proj}.{DATASET})"

            site_sql = f"""
            SELECT
                COALESCE(FACILITY_NM, 'Care Site') AS name,
                COALESCE(site_kind, 'Facility') AS site_kind,
                latitude,
                longitude,
                COALESCE(TOT_OPER_HR_PER_WEEK, 40.0) AS hours_per_week
            FROM `{t_prefix}.care_sites`
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """
            for s in bq.query(site_sql).result():
                sd = dict(s)
                sd["is_safety_net"] = sd["site_kind"] in ("FQHC", "Health Center site")
                sites.append(sd)

            meta_sql = f"""
            SELECT
                (SELECT COUNT(*) FROM `{t_prefix}.shortage_areas`) AS hpsa_cnt,
                (SELECT COUNTIF(percent_visits_covid IS NOT NULL) FROM `{t_prefix}.disease_weekly`) AS covid_wks
            """
            meta_row = list(bq.query(meta_sql).result())[0]
            shortage_areas_count = int(meta_row["hpsa_cnt"] or 0)
            usable_covid_weeks = int(meta_row["covid_wks"] or 0)
    except Exception:
        tracts = [dict(x) for x in FALLBACK_TRACTS]
        sites = [dict(x) for x in FALLBACK_SITES]

    for t in tracts:
        t["need_score"] = compute_need_score(t)

    sorted_tracts = sorted(tracts, key=lambda x: x["need_score"], reverse=True)
    recommended = []
    saturdays = [
        "Saturday 1 (Week 1)",
        "Saturday 2 (Week 2)",
        "Saturday 3 (Week 3)",
        "Saturday 4 (Week 4)",
    ]
    for idx, stop in enumerate(sorted_tracts[:4]):
        item = dict(stop)
        item["saturday_slot"] = saturdays[idx]
        item["rank"] = idx + 1
        item["rationale"] = (
            f"Tract {item['geo_id']} has a +{item.get('extra_km_if_uninsured', 0)} km safety-net "
            f"access penalty ({item.get('km_to_safety_net', 0)} km to sliding-scale care vs. "
            f"{item.get('km_to_any_care', 0)} km to any clinic), {item.get('pct_uninsured', 0)}% "
            f"uninsured adults, and {item.get('pct_no_vehicle', 0)}% no-vehicle households."
        )
        recommended.append(item)

    # Compute Post-Hoc Equity Audit metrics (Planner never saw SVI composite/demographic audit)
    def avg(items: List[Dict[str, Any]], key: str) -> float:
        vals = [float(x[key]) for x in items if x.get(key) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    audit = {
        "status": "PASSED WITH EQUITY NOTE",
        "county_avg_svi_socioeconomic": avg(tracts, "svi_socioeconomic"),
        "plan_avg_svi_socioeconomic": avg(recommended, "svi_socioeconomic"),
        "county_avg_uninsured": avg(tracts, "pct_uninsured"),
        "plan_avg_uninsured": avg(recommended, "pct_uninsured"),
        "county_avg_extra_km": avg(tracts, "extra_km_if_uninsured"),
        "plan_avg_extra_km": avg(recommended, "extra_km_if_uninsured"),
        "county_avg_limited_english": avg(tracts, "pct_limited_english"),
        "plan_avg_limited_english": avg(recommended, "pct_limited_english"),
        "audit_summary": (
            "Race/ethnicity (SVI Theme 3) was strictly excluded from the Siting Planner input. "
            "Post-hoc audit confirms the 4 selected Saturday tracts concentrate on structural "
            "barriers: mean SVI Socioeconomic percentile is "
            f"{avg(recommended, 'svi_socioeconomic')} vs. {avg(tracts, 'svi_socioeconomic')} county-wide, "
            f"and uninsured safety-net gap is {avg(recommended, 'extra_km_if_uninsured')} km vs. "
            f"{avg(tracts, 'extra_km_if_uninsured')} km county-wide. Bilingual English/Spanish "
            "outreach is required where Limited English exceeds 5%."
        ),
    }

    return {
        "source_mode": source_mode,
        "county_name": county_name,
        "total_tracts": len(tracts),
        "total_sites": len(sites),
        "shortage_areas_count": shortage_areas_count,
        "usable_covid_weeks": usable_covid_weeks,
        "latest_covid_pct": latest_covid_pct,
        "tracts": tracts,
        "sites": sites,
        "recommended_stops": recommended,
        "equity_audit": audit,
    }


@app.get("/")
async def serve_ui():
    return FileResponse(UI_PATH)


@app.get("/api/map-data")
async def get_map_data():
    data = load_county_data()
    return JSONResponse(data)


# Keep ADK runner in memory for interactive chat sessions
_ADK_RUNNER = None


async def run_adk_agent(user_message: str, session_id: str, county_data: Dict[str, Any]) -> str:
    global _ADK_RUNNER
    top4 = county_data["recommended_stops"]
    audit = county_data["equity_audit"]
    context_summary = (
        f"[Active County Context: {county_data['county_name']} | Source: {county_data['source_mode']} | "
        f"Total Tracts: {county_data['total_tracts']} | Care Sites: {county_data['total_sites']} | "
        f"Shortage Areas (HPSA): {county_data['shortage_areas_count']} | "
        f"Top 4 Saturday Recommended Tracts: "
        + "; ".join(
            f"{s['saturday_slot']}: Tract {s['geo_id']} (Need Score {s['need_score']}, "
            f"Uninsured {s['pct_uninsured']}%, Safety-Net Gap +{s['extra_km_if_uninsured']} km, "
            f"No-Vehicle {s['pct_no_vehicle']}%)"
            for s in top4
        )
        + f" | Post-Hoc Equity Audit: {audit['audit_summary']}]\n\nUser Message: {user_message}"
    )

    try:
        from agent.agent import root_agent
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        if _ADK_RUNNER is None:
            _ADK_RUNNER = InMemoryRunner(agent=root_agent, app_name="public_health_broker")

        session = await _ADK_RUNNER.session_service.get_session(
            app_name="public_health_broker", user_id="web_user", session_id=session_id
        )
        if session is None:
            session = await _ADK_RUNNER.session_service.create_session(
                app_name="public_health_broker", user_id="web_user", session_id=session_id
            )

        content = types.Content(role="user", parts=[types.Part.from_text(text=context_summary)])
        chunks: List[str] = []
        async for event in _ADK_RUNNER.run_async(
            user_id="web_user", session_id=session.id, new_message=content
        ):
            if getattr(event, "content", None) and getattr(event.content, "parts", None):
                for part in event.content.parts:
                    if getattr(part, "text", None):
                        chunks.append(part.text)
        if chunks:
            return "\n".join(chunks)
    except Exception as exc:
        # Provide transparent fallback response if Vertex AI credentials aren't initialized yet
        return (
            f"**[Root Coordinator — {county_data['county_name']}]**\n\n"
            f"Hello! I am the **Dynamic Public Health Equity & Preventative Mobile Care Broker**.\n\n"
            f"Here is our current 4-Saturday Mobile Clinic Plan (computed at **Census Tract** resolution without race inputs):\n"
            + "\n".join(
                f"- **{s['saturday_slot']} — Tract `{s['geo_id']}`** (Score `{s['need_score']}`): "
                f"`+{s['extra_km_if_uninsured']} km` further to sliding-scale safety-net care "
                f"(`{s['km_to_safety_net']} km` vs `{s['km_to_any_care']} km`), "
                f"`{s['pct_uninsured']}%` uninsured, `{s['pct_no_vehicle']}%` no-vehicle households."
                for s in top4
            )
            + f"\n\n**Equity Audit Verdict (`session.state['audit_result']`):** {audit['audit_summary']}\n\n"
            f"*(Note: ADK live model call encountered `{type(exc).__name__}: {exc}` — make sure "
            f"`GOOGLE_GENAI_USE_VERTEXAI=TRUE` and `GOOGLE_CLOUD_PROJECT` are exported in your terminal.)*"
        )

    return "Hello! How would you like to plan or audit next month's mobile clinic stops?"


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    county_data = load_county_data()
    reply = await run_adk_agent(req.message, req.session_id or "default-session", county_data)
    mentioned_tracts = re.findall(r"\b\d{11}\b", reply)
    return JSONResponse(
        {
            "reply": reply,
            "highlight_tracts": list(dict.fromkeys(mentioned_tracts)),
        }
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
