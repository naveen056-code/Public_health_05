"""Web server: ADK's API, the planner's interface at /, the community page at /community,
and ADK's developer UI kept at /dev-ui/.

Run locally from this folder:  uvicorn main:app --port 8080
"""

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
# Load the agent's settings before importing it: config.py reads the environment at import.
load_dotenv(HERE / "clinic_broker" / ".env", override=False)

import json  # noqa: E402
import re  # noqa: E402

import httpx  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from google.adk.cli.fast_api import get_fast_api_app  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from clinic_broker import data  # noqa: E402

app = get_fast_api_app(
    agents_dir=str(HERE),
    session_service_uri="memory://",
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


@app.get("/community", include_in_schema=False)
async def community():
    return FileResponse(HERE / "ui" / "community.html")


@app.get("/api/map")
async def map_layers():
    try:
        return data.map_layers()
    except Exception as e:  # surface BigQuery problems to the page instead of a bare 500
        raise HTTPException(status_code=503, detail=f"Could not load map data: {e}") from e


class PublishRequest(BaseModel):
    user_id: str = ""
    session_id: str = ""
    sample: bool = False


@app.post("/api/publish")
async def publish(req: PublishRequest):
    """Publishes a finished plan to the community page. The plan is read from the agents'
    own session on this server, never taken from the request body, so what residents see
    is what the planner and auditor produced."""
    if req.sample:
        state = json.loads((HERE / "ui" / "sample_run.json").read_text())["state"]
    elif not (re.fullmatch(r"[\w-]{1,80}", req.user_id) and re.fullmatch(r"[\w-]{1,80}", req.session_id)):
        raise HTTPException(status_code=400, detail="user_id and session_id are required")
    else:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://local") as c:
            r = await c.get(f"/apps/clinic_broker/users/{req.user_id}/sessions/{req.session_id}")
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="That planning session is not on this server anymore.")
        state = r.json().get("state", {})
    try:
        return data.publish_plan(data.publishable(state))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/published")
async def published():
    plan = data.latest_published()
    if not plan:
        raise HTTPException(status_code=404, detail="No plan has been published yet.")
    return plan


@app.get("/api/my-stop")
async def my_stop(geo_id: str):
    if not re.fullmatch(r"\d{11}", geo_id):
        raise HTTPException(status_code=400, detail="geo_id must be an 11-digit tract code")
    return data.stop_for_tract(geo_id)


@app.middleware("http")
async def revalidate_pages(request, call_next):
    """Make browsers re-check the pages and scripts on every load, so a redeploy is never
    hidden behind a cached old copy (a cached app.js once hid the race-guideline banner)."""
    response = await call_next(request)
    if request.url.path in ("/", "/community") or request.url.path.startswith("/ui/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/ui", StaticFiles(directory=HERE / "ui"), name="ui")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
