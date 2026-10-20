"""Settings, read from the environment so the same code runs locally and on Cloud Run."""

import os
import subprocess


def _detect_project() -> str:
    proj = (
        os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("DEVSHELL_PROJECT_ID")
        or os.environ.get("GCLOUD_PROJECT")
        or os.environ.get("GCP_PROJECT")
    )
    if not proj:
        try:
            proj = subprocess.check_output(
                ["gcloud", "config", "get-value", "project"],
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip()
        except Exception:
            proj = ""
    if proj and proj != "(unset)":
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", proj)
        return proj
    return ""


# Gemini 3.x answers only on the `global` location in the lab project; a regional
# location returns "model not found", which looks like a permissions problem and is not.
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")

PROJECT = _detect_project()
DATASET = os.environ.get("A4I_DATASET", "a4i_health")
BQ_LOCATION = os.environ.get("A4I_BQ_LOCATION", "US")

# The county the tables in DATASET were loaded for. load.sh and the notebook load one
# county at a time, so this must match whatever was loaded last.
COUNTY_FIPS = os.environ.get("A4I_COUNTY_FIPS", "13121")
COUNTY_NAME = os.environ.get("A4I_COUNTY_NAME", "Fulton County, GA")

MODEL = os.environ.get("A4I_MODEL", "gemini-3.6-flash")

# Race and ethnicity live here, and only the auditor is given a tool that can read it.
ACS_TABLE = "bigquery-public-data.census_bureau_acs.censustract_2020_5yr"

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"


def table(name: str) -> str:
    return f"`{PROJECT}.{DATASET}.{name}`" if PROJECT else f"`{DATASET}.{name}`"
