"""Settings, read from the environment so the same code runs locally and on Cloud Run."""

import os

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
DATASET = os.environ.get("A4I_DATASET", "a4i_health")
BQ_LOCATION = os.environ.get("A4I_BQ_LOCATION", "US")

# The county the tables in DATASET were loaded for. load.sh and the notebook load one
# county at a time, so this must match whatever was loaded last.
COUNTY_FIPS = os.environ.get("A4I_COUNTY_FIPS", "13121")
COUNTY_NAME = os.environ.get("A4I_COUNTY_NAME", "Fulton County, GA")

# Gemini 3.x answers only on the `global` location in the lab project; a regional
# location returns "model not found", which looks like a permissions problem and is not.
MODEL = os.environ.get("A4I_MODEL", "gemini-3.6-flash")

# Race and ethnicity live here, and only the auditor is given a tool that can read it.
ACS_TABLE = "bigquery-public-data.census_bureau_acs.censustract_2020_5yr"

BIGQUERY_MCP_URL = "https://bigquery.googleapis.com/mcp"


def table(name: str) -> str:
    return f"`{PROJECT}.{DATASET}.{name}`"
