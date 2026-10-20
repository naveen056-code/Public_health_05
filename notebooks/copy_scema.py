import os
import json
from pathlib import Path
from google.cloud import bigquery

# Uses your environment project ID or notebook default
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", PROJECT if "PROJECT" in locals() else "qwiklabs-gcp-04-9ac0749d9f02")
DATASET_ID = "a4i_health"
OUTPUT_DIR = Path("schemas")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

client = bigquery.Client(project=PROJECT_ID)
dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)

all_schemas = {}
for item in client.list_tables(dataset_ref):
    table = client.get_table(item.reference)
    schema_list = [
        {"name": f.name, "type": f.field_type, "mode": f.mode, "description": f.description or ""}
        for f in table.schema
    ]
    all_schemas[table.table_id] = schema_list
    
    # Write individual table schema
    with open(OUTPUT_DIR / f"{table.table_id}.schema.json", "w", encoding="utf-8") as f:
        json.dump(schema_list, f, indent=2)

# Write combined JSON schema file
with open(OUTPUT_DIR / "all_tables_schema.json", "w", encoding="utf-8") as f:
    json.dump(all_schemas, f, indent=2)

print(f"Successfully saved schemas for {len(all_schemas)} tables to {OUTPUT_DIR.resolve()}/")