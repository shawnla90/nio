"""NIO Dashboard: FastAPI + HTMX + Alpine + Chart.js.

Serves localhost:4242. No npm build step. Single Python process.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="NIO Dashboard", docs_url=None, redoc_url=None)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Now Playing: the home page hero."""
    from nio.core.metrics import get_recent_slop_avg
    from nio.core.soul import get_active_soul
    from nio.core.voice import get_active_voice

    return templates.TemplateResponse(
        request=request, name="index.html",
        context={
            "soul": get_active_soul() or "none",
            "voice": get_active_voice() or "none",
            "slop_avg": get_recent_slop_avg() or 0,
        },
    )


@app.get("/souls/diff", response_class=HTMLResponse)
async def soul_diff(request: Request, a: str = "", b: str = ""):
    """Soul diff viewer."""
    return templates.TemplateResponse(
        request=request, name="soul_diff.html",
        context={"ref_a": a, "ref_b": b},
    )


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    """Metrics explorer."""
    return templates.TemplateResponse(request=request, name="metrics.html")


@app.get("/team", response_class=HTMLResponse)
async def team_page(request: Request):
    """Team activity."""
    return templates.TemplateResponse(request=request, name="team.html")


@app.get("/registry", response_class=HTMLResponse)
async def registry_page(request: Request):
    """Registry browser."""
    return templates.TemplateResponse(request=request, name="registry.html")


@app.get("/gateway", response_class=HTMLResponse)
async def gateway_page(request: Request):
    """Gateway status."""
    return templates.TemplateResponse(request=request, name="gateway.html")


# --- API endpoints for HTMX ---

@app.get("/api/metrics/recent")
async def api_recent_metrics(window: str = "7d"):
    from nio.core.metrics import query_metrics
    return JSONResponse(query_metrics(window=window))


@app.get("/api/turns/recent")
async def api_recent_turns(limit: int = 10, platform: str = ""):
    """Return the most recent turns for the live feed.

    Optional ?platform= filter (e.g., 'claude_code' or 'discord').
    """
    from nio.core.db import get_connection

    conn = get_connection()

    if platform:
        rows = conn.execute(
            "SELECT t.turn_id, t.session_id, t.slop_score, t.latency_ms, "
            "t.slop_violations, t.created_at, s.platform "
            "FROM turns t JOIN sessions s ON t.session_id = s.session_id "
            "WHERE s.platform = ? ORDER BY t.created_at DESC LIMIT ?",
            (platform, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT t.turn_id, t.session_id, t.slop_score, t.latency_ms, "
            "t.slop_violations, t.created_at, s.platform "
            "FROM turns t LEFT JOIN sessions s ON t.session_id = s.session_id "
            "ORDER BY t.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()

    import json
    turns = []
    for r in rows:
        turns.append({
            "turn_id": r[0],
            "session_id": r[1],
            "slop_score": r[2],
            "latency_ms": r[3],
            "violations": json.loads(r[4]) if r[4] else [],
            "created_at": r[5],
            "platform": r[6] or "unknown",
        })
    return JSONResponse(turns)


@app.get("/api/souls")
async def api_souls():
    from nio.core.soul import list_souls
    return JSONResponse(list_souls())


@app.get("/api/voices")
async def api_voices():
    from nio.core.voice import list_voices
    return JSONResponse(list_voices())


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Live dashboard WebSocket. Middleware pushes turn events here."""
    from nio.dash.ws import connect
    await connect(websocket)


def main():
    """Run the dashboard server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=4242, log_level="warning")


if __name__ == "__main__":
    main()
