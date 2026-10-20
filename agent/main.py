"""Web server: ADK's API, our interface at /, and ADK's developer UI kept at /dev-ui/.

Run locally from this folder:  uvicorn main:app --port 8080
"""

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
# Load the agent's settings before importing it: config.py reads the environment at import.
load_dotenv(HERE / "clinic_broker" / ".env", override=False)

from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from google.adk.cli.fast_api import get_fast_api_app  # noqa: E402

from clinic_broker import data  # noqa: E402

app = get_fast_api_app(
    agents_dir=str(HERE),
    session_service_uri="sqlite:////tmp/sessions.db",
    artifact_service_uri="memory://",
    use_local_storage=False,
    web=True,
)

# ADK redirects "/" to its developer UI. Ours takes "/"; the developer UI stays at
# /dev-ui/, which is still the best view of the event graph.
app.router.routes = [r for r in app.router.routes if getattr(r, "path", None) != "/"]


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(HERE / "ui" / "index.html")


@app.get("/api/map")
async def map_layers():
    try:
        return data.map_layers()
    except Exception as e:  # surface BigQuery problems to the page instead of a bare 500
        raise HTTPException(status_code=503, detail=f"Could not load map data: {e}") from e


app.mount("/ui", StaticFiles(directory=HERE / "ui"), name="ui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
