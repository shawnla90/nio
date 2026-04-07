"""NIO Dashboard: FastAPI + HTMX + Alpine + Chart.js.

Serves localhost:4242. No npm build step. Single Python process.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(title="NIO Dashboard", docs_url=None, redoc_url=None)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _ctx(request: Request, page: str, **extra):
    """Build template context with active_page for nav highlighting."""
    return {"request": request, "active_page": page, **extra}


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# --- Page routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Home: command center hub."""
    from nio.core.metrics import get_recent_slop_avg
    from nio.core.soul import get_active_soul
    from nio.core.voice import get_active_voice

    soul = get_active_soul() or "none"
    voice = get_active_voice() or "none"
    slop_avg = get_recent_slop_avg() or 0

    session_count = turn_count = memory_count = 0
    try:
        from nio.core.db import get_connection
        conn = get_connection()
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        turn_count = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        try:
            memory_count = conn.execute("SELECT COUNT(*) FROM memory_context").fetchone()[0]
        except Exception:
            pass
        conn.close()
    except Exception:
        pass

    platforms_connected = 0
    try:
        from nio.core.platform_probe import probe_all
        platforms_connected = sum(1 for p in probe_all() if p["configured"])
    except Exception:
        pass

    setup_needed = (soul == "none" and session_count == 0) or turn_count == 0

    return templates.TemplateResponse(
        request=request, name="index.html",
        context=_ctx(request, "home",
                     soul=soul, voice=voice, slop_avg=slop_avg,
                     setup_needed=setup_needed, session_count=session_count,
                     turn_count=turn_count, platforms_connected=platforms_connected,
                     memory_count=memory_count),
    )


@app.get("/soul", response_class=HTMLResponse)
async def soul_page(request: Request):
    """Soul viewer: active soul content and version history."""
    from nio.core.soul import get_active_soul, load_soul

    soul_ref = get_active_soul() or ""
    soul_id = soul_ref.split("@")[0] if soul_ref else ""
    soul_data = load_soul(soul_id) if soul_id else None

    # Version history from DB
    versions = []
    if soul_id:
        try:
            from nio.core.db import get_connection
            conn = get_connection()
            rows = conn.execute(
                "SELECT version, released_at, changelog FROM soul_versions "
                "WHERE soul_id = ? ORDER BY released_at DESC",
                (soul_id,),
            ).fetchall()
            versions = [{"version": r[0], "released_at": r[1], "changelog": r[2]} for r in rows]
            conn.close()
        except Exception:
            pass

    return templates.TemplateResponse(
        request=request, name="soul.html",
        context=_ctx(request, "soul", soul_id=soul_id, soul_data=soul_data, versions=versions),
    )


@app.get("/memory", response_class=HTMLResponse)
async def memory_page(request: Request):
    """Memory browser: all imported memory entries."""
    stats = {"total": 0, "hermes_memory": 0, "hermes_user": 0, "claude_handoff": 0}
    try:
        from nio.core.db import get_connection
        conn = get_connection()
        rows = conn.execute(
            "SELECT source, COUNT(*) FROM memory_context GROUP BY source"
        ).fetchall()
        for source, count in rows:
            stats[source] = count
            stats["total"] += count
        conn.close()
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request, name="memory.html",
        context=_ctx(request, "memory", stats=stats),
    )


@app.get("/sessions", response_class=HTMLResponse)
async def sessions_page(request: Request):
    """Session history list."""
    sessions = []
    try:
        from nio.core.db import get_connection
        conn = get_connection()
        rows = conn.execute(
            "SELECT s.session_id, s.soul_id, s.platform, s.task_type, "
            "s.started_at, s.ended_at, "
            "COUNT(t.turn_id) as turn_count, AVG(t.slop_score) as slop_avg "
            "FROM sessions s LEFT JOIN turns t ON s.session_id = t.session_id "
            "GROUP BY s.session_id ORDER BY s.started_at DESC LIMIT 100"
        ).fetchall()
        for r in rows:
            sessions.append({
                "session_id": r[0], "soul_id": r[1], "platform": r[2],
                "task_type": r[3], "started_at": r[4], "ended_at": r[5],
                "turn_count": r[6], "slop_avg": r[7],
            })
        conn.close()
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request, name="sessions.html",
        context=_ctx(request, "sessions", sessions=sessions),
    )


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
async def session_detail_page(request: Request, session_id: str):
    """Session detail with turn-by-turn timeline."""
    session = {}
    turns = []
    slop_avg = None
    try:
        from nio.core.db import get_connection
        conn = get_connection()
        row = conn.execute(
            "SELECT session_id, soul_id, soul_version, voice_id, platform, "
            "task_type, started_at, ended_at FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if row:
            session = {
                "session_id": row[0], "soul_id": row[1], "soul_version": row[2],
                "voice_id": row[3], "platform": row[4], "task_type": row[5],
                "started_at": row[6], "ended_at": row[7],
            }
        turn_rows = conn.execute(
            "SELECT turn_index, user_msg, agent_msg, latency_ms, slop_score, "
            "slop_violations, created_at FROM turns WHERE session_id = ? "
            "ORDER BY turn_index",
            (session_id,),
        ).fetchall()
        for t in turn_rows:
            turns.append({
                "turn_index": t[0], "user_msg": t[1], "agent_msg": t[2],
                "latency_ms": t[3], "slop_score": t[4],
                "violations": json.loads(t[5]) if t[5] else [],
                "created_at": t[6],
            })
        avg_row = conn.execute(
            "SELECT AVG(slop_score) FROM turns WHERE session_id = ? AND slop_score IS NOT NULL",
            (session_id,),
        ).fetchone()
        slop_avg = avg_row[0] if avg_row and avg_row[0] else None
        conn.close()
    except Exception:
        pass

    return templates.TemplateResponse(
        request=request, name="session_detail.html",
        context=_ctx(request, "sessions", session=session, turns=turns, slop_avg=slop_avg),
    )


@app.get("/gateway", response_class=HTMLResponse)
async def gateway_page(request: Request):
    """Connection manager with live platform status."""
    platforms = []
    whatsapp_bridge = None
    try:
        from nio.core.platform_probe import check_whatsapp_bridge, probe_all
        platforms = probe_all()
        bridge = check_whatsapp_bridge()
        whatsapp_bridge = str(bridge) if bridge else None
    except Exception:
        pass

    hermes_hook = Path.home().joinpath(".hermes", "hooks", "nio", "HOOK.yaml").is_file()
    cc_skill = Path.home().joinpath(".claude", "skills", "nio", "SKILL.md").is_file()

    return templates.TemplateResponse(
        request=request, name="gateway.html",
        context=_ctx(request, "connections",
                     platforms=platforms, whatsapp_bridge=whatsapp_bridge,
                     hermes_hook=hermes_hook, cc_skill=cc_skill),
    )


@app.get("/souls/diff", response_class=HTMLResponse)
async def soul_diff(request: Request, a: str = "", b: str = ""):
    return templates.TemplateResponse(
        request=request, name="soul_diff.html",
        context=_ctx(request, "soul", ref_a=a, ref_b=b),
    )


@app.get("/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="metrics.html",
        context=_ctx(request, "metrics"),
    )


@app.get("/team", response_class=HTMLResponse)
async def team_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="team.html",
        context=_ctx(request, "team"),
    )


@app.get("/registry", response_class=HTMLResponse)
async def registry_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="registry.html",
        context=_ctx(request, "registry"),
    )


@app.get("/learn", response_class=HTMLResponse)
async def learn_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="learn.html",
        context=_ctx(request, "learn"),
    )


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Chat interface: talk to your agent via Claude Code."""
    from nio.core.soul import get_active_soul
    soul = get_active_soul() or "nio-core"
    return templates.TemplateResponse(
        request=request, name="chat.html",
        context=_ctx(request, "chat", soul=soul),
    )


@app.post("/api/chat")
async def api_chat(request: Request):
    """SSE endpoint: spawn Claude Code, stream response, score for slop."""
    import asyncio

    data = await request.json()
    message = data.get("message", "")
    resume_session = data.get("session_id")

    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)

    # Build soul prompt path
    soul_path = Path.home() / ".nio" / "active" / "soul-prompt.md"
    try:
        from nio.core.soul import get_active_soul, load_soul
        ref = get_active_soul() or ""
        soul_id = ref.split("@")[0] if ref else ""
        if soul_id:
            soul_data = load_soul(soul_id)
            if soul_data and soul_data.get("body"):
                soul_path.parent.mkdir(parents=True, exist_ok=True)
                soul_path.write_text(soul_data["body"])
    except Exception:
        pass

    # Build Claude CLI args
    import shutil
    claude_bin = shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude")
    args = [
        claude_bin,
        "-p", message,
        "--output-format", "stream-json",
        "--verbose",
        "--max-turns", "10",
    ]
    if soul_path.exists() and soul_path.stat().st_size > 0:
        args.extend(["--append-system-prompt-file", str(soul_path)])
    if resume_session:
        args.extend(["--resume", resume_session])

    async def stream_response():
        # Spawn Claude Code
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                **__import__("os").environ,
                "CLAUDECODE": "",
                "PATH": f"{Path.home() / '.local' / 'bin'}:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            },
        )

        full_response = ""
        captured_session_id = None

        try:
            buffer = ""
            while True:
                chunk = await asyncio.wait_for(proc.stdout.read(4096), timeout=180)
                if not chunk:
                    break

                buffer += chunk.decode()
                lines = buffer.split("\n")
                buffer = lines.pop()

                for line in lines:
                    if not line.strip():
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Capture session ID
                    if not captured_session_id and event.get("session_id"):
                        captured_session_id = event["session_id"]
                        yield f"data: {json.dumps({'type': 'session_id', 'session_id': captured_session_id})}\n\n"

                    # Extract text from assistant messages
                    if event.get("type") == "assistant":
                        msg = event.get("message", {})
                        for block in msg.get("content", []):
                            if block.get("type") == "text" and block.get("text"):
                                text = block["text"]
                                full_response += text
                                yield f"data: {json.dumps({'type': 'text', 'text': text})}\n\n"

                    # Extract text from result event (final response)
                    if event.get("type") == "result":
                        result_text = event.get("result", "")
                        if result_text and not full_response:
                            full_response = result_text
                            yield f"data: {json.dumps({'type': 'text', 'text': result_text})}\n\n"
                        elif result_text and result_text != full_response:
                            # Result may have additional text
                            extra = result_text[len(full_response):]
                            if extra:
                                full_response = result_text
                                yield f"data: {json.dumps({'type': 'text', 'text': extra})}\n\n"

        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout waiting for response'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        # Wait for process to finish
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except Exception:
            pass

        # Score the full response
        slop_score = 100.0
        try:
            from nio.core.antislop import score
            slop_score = score(full_response) if full_response else 100.0
        except Exception:
            pass

        # Record turn
        try:
            from nio.claude_code.session_bridge import record_cc_turn, start_cc_session
            nio_session = start_cc_session()
            record_cc_turn(nio_session, user_msg=message, agent_msg=full_response)
        except Exception:
            pass

        yield f"data: {json.dumps({'type': 'done', 'slop_score': slop_score})}\n\n"
        yield "data: [DONE]\n\n"

        # Clean up
        try:
            if proc.returncode is None:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- API endpoints ---

@app.get("/api/metrics/recent")
async def api_recent_metrics(window: str = "7d"):
    from nio.core.metrics import query_metrics
    return JSONResponse(query_metrics(window=window))


@app.get("/api/turns/recent")
async def api_recent_turns(limit: int = 10, platform: str = ""):
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
    turns = []
    for r in rows:
        turns.append({
            "turn_id": r[0], "session_id": r[1], "slop_score": r[2],
            "latency_ms": r[3], "violations": json.loads(r[4]) if r[4] else [],
            "created_at": r[5], "platform": r[6] or "unknown",
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


@app.get("/api/soul/active")
async def api_soul_active():
    from nio.core.soul import get_active_soul, load_soul
    ref = get_active_soul() or ""
    soul_id = ref.split("@")[0] if ref else ""
    data = load_soul(soul_id) if soul_id else None
    if data:
        return JSONResponse({"soul_id": soul_id, "metadata": data.get("metadata", {}), "body": data.get("body", "")})
    return JSONResponse({"soul_id": "", "metadata": {}, "body": ""})


@app.get("/api/memory")
async def api_memory(source: str = "", page: int = 1, per_page: int = 30):
    from nio.core.db import get_connection
    conn = get_connection()
    offset = (page - 1) * per_page
    try:
        if source:
            rows = conn.execute(
                "SELECT context_id, source, content, imported_at, tags "
                "FROM memory_context WHERE source = ? ORDER BY imported_at DESC LIMIT ? OFFSET ?",
                (source, per_page, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT context_id, source, content, imported_at, tags "
                "FROM memory_context ORDER BY imported_at DESC LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
    except Exception:
        rows = []
    conn.close()

    # Return as HTML fragments for HTMX
    html_parts = []
    for r in rows:
        source_badge = r[1].replace("_", " ").title()
        content = r[2][:200] + ("..." if len(r[2]) > 200 else "")
        html_parts.append(
            f'<div class="memory-entry">'
            f'<span class="memory-source">{source_badge}</span>'
            f'<span class="memory-date dim">{(r[3] or "")[:10]}</span>'
            f'<p class="memory-content">{content}</p>'
            f'</div>'
        )

    if not html_parts:
        html_parts.append('<p class="dim">No memory entries found.</p>')

    return HTMLResponse("\n".join(html_parts))


@app.get("/api/memory/stats")
async def api_memory_stats():
    from nio.core.db import get_connection
    stats = {"total": 0, "hermes_memory": 0, "hermes_user": 0, "claude_handoff": 0}
    try:
        conn = get_connection()
        rows = conn.execute("SELECT source, COUNT(*) FROM memory_context GROUP BY source").fetchall()
        for source, count in rows:
            stats[source] = count
            stats["total"] += count
        conn.close()
    except Exception:
        pass
    return JSONResponse(stats)


@app.post("/api/memory/import/hermes")
async def api_import_hermes():
    from nio.core.memory import import_hermes_memories
    count = import_hermes_memories()
    return JSONResponse({"imported": count})


@app.post("/api/memory/import/handoffs")
async def api_import_handoffs():
    from nio.core.memory import import_claude_handoffs
    count = import_claude_handoffs()
    return JSONResponse({"imported": count})


@app.get("/api/sessions")
async def api_sessions(platform: str = "", limit: int = 50):
    from nio.core.db import get_connection
    conn = get_connection()
    if platform:
        rows = conn.execute(
            "SELECT session_id, soul_id, platform, task_type, started_at, ended_at "
            "FROM sessions WHERE platform = ? ORDER BY started_at DESC LIMIT ?",
            (platform, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT session_id, soul_id, platform, task_type, started_at, ended_at "
            "FROM sessions ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    conn.close()
    return JSONResponse([{
        "session_id": r[0], "soul_id": r[1], "platform": r[2],
        "task_type": r[3], "started_at": r[4], "ended_at": r[5],
    } for r in rows])


@app.post("/api/gateway/configure")
async def api_configure_platform(request: Request):
    data = await request.json()
    platform = data.get("platform", "")
    token = data.get("token", "")
    if not platform or not token:
        return JSONResponse({"error": "platform and token required"}, status_code=400)
    from nio.core.platform_probe import configure_platform
    configure_platform(platform, token)
    return JSONResponse({"status": "ok", "platform": platform})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    from nio.dash.ws import connect
    await connect(websocket)


def main():
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=4242, log_level="warning")


if __name__ == "__main__":
    main()
