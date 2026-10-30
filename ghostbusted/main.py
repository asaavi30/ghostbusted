# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""FastAPI app. Run:  uvicorn ghostbusted.main:app --reload"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from fastapi import File, UploadFile

from . import analyzer, config, daily, db, odds, radar, resume_files, skills, streaks

logging.basicConfig(level=logging.INFO)
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="GhostBusted")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

STATUSES = {"saved", "applied", "interviewing", "offer", "rejected", "ghosted"}


class AnalyzeIn(BaseModel):
    url: str | None = None
    text: str | None = None


class StatusIn(BaseModel):
    status: str


class ProfileIn(BaseModel):
    resume: str = ""
    goals: str = ""
    daily_goal: str = "1"
    motivation: str = "both"  # tough | kind | both


# ---------- credit protection for the public demo ----------
import time
from collections import defaultdict, deque

from fastapi import Request

_hits: dict[str, deque] = defaultdict(deque)
_all: deque = deque()


def _visitor(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def spend_credit(request: Request) -> None:
    """Call before any action that uses Nebius or Tavily credits. Raises 429 when a limit is hit."""
    if not (config.LIMIT_PER_VISITOR or config.LIMIT_TOTAL) or config.DEMO_MODE:
        return
    now_t, day = time.time(), 86400
    q = _hits[_visitor(request)]
    for d in (q, _all):
        while d and now_t - d[0] > day:
            d.popleft()
    if config.LIMIT_TOTAL and len(_all) >= config.LIMIT_TOTAL:
        raise HTTPException(429, "The public demo has hit today's limit. Run GhostBusted locally (see the README) to keep going.")
    if config.LIMIT_PER_VISITOR and len(q) >= config.LIMIT_PER_VISITOR:
        raise HTTPException(429, f"Demo limit reached: {config.LIMIT_PER_VISITOR} live checks per visitor per day. "
                                 "Run GhostBusted locally (see the README) for unlimited checks.")
    q.append(now_t)
    _all.append(now_t)


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
async def health():
    return {"ok": True, "demo": config.DEMO_MODE, "public": config.PUBLIC,
            "limit_per_visitor": config.LIMIT_PER_VISITOR,
            "models": {"nano": config.MODEL_NANO, "super": config.MODEL_SUPER, "ultra": config.MODEL_ULTRA}}


@app.post("/api/analyze")
async def analyze(body: AnalyzeIn, request: Request):
    if not (body.url or body.text):
        raise HTTPException(400, "Send a job URL or the posting text.")
    spend_credit(request)
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(ev):
        await queue.put(ev)

    async def worker():
        try:
            profile = db.get_profile()
            report, posting = await analyzer.analyze(body.url, body.text, profile, emit)
            report = await asyncio.to_thread(radar.apply, report)
            report["keywords"] = skills.match(report.get("job") or {}, profile.get("resume") or "")
            app_id = await asyncio.to_thread(db.save_application, report, body.url, posting)
            hist = await asyncio.to_thread(db.company_history, (report.get("job") or {}).get("company") or "")
            await queue.put({"type": "result", "id": app_id, "report": report,
                             "company_history": hist[0] if hist else None})
        except Exception as e:
            logging.exception("analyze failed")
            await queue.put({"type": "error", "message": str(e)})
        finally:
            await queue.put(None)

    async def stream():
        task = asyncio.create_task(worker())
        try:
            while (ev := await queue.get()) is not None:
                yield f"data: {json.dumps(ev)}\n\n"
        finally:
            task.cancel() if not task.done() else None

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/applications")
async def applications():
    return await asyncio.to_thread(db.list_applications)


@app.get("/api/applications/{app_id}")
async def application(app_id: int):
    a = await asyncio.to_thread(db.get_application, app_id)
    if not a:
        raise HTTPException(404)
    a.pop("posting_text", None)
    return a


@app.patch("/api/applications/{app_id}")
async def set_status(app_id: int, body: StatusIn):
    if body.status not in STATUSES:
        raise HTTPException(400, f"status must be one of {sorted(STATUSES)}")
    await asyncio.to_thread(db.update_status, app_id, body.status)
    return {"ok": True}


@app.delete("/api/applications/{app_id}")
async def delete(app_id: int):
    await asyncio.to_thread(db.delete_application, app_id)
    return {"ok": True}


@app.post("/api/applications/{app_id}/followup")
async def followup(app_id: int, request: Request):
    a = await asyncio.to_thread(db.get_application, app_id)
    if not a:
        raise HTTPException(404)
    spend_credit(request)
    return {"draft": await analyzer.draft_followup(a, db.get_profile())}


@app.post("/api/applications/{app_id}/followup/sent")
async def followup_sent(app_id: int):
    await asyncio.to_thread(db.mark_followup_sent, app_id)
    return {"ok": True}


@app.get("/api/applications/{app_id}/keywords")
async def keywords(app_id: int):
    """Re-compare a job's skills with your CURRENT resume (free: no API calls)."""
    a = await asyncio.to_thread(db.get_application, app_id)
    if not a:
        raise HTTPException(404)
    job = (a.get("report") or {}).get("job") or {}
    return {"keywords": skills.match(job, db.get_profile().get("resume") or "")}


@app.get("/api/best-bets")
async def best_bets():
    """Jobs you haven't applied to yet, ranked by reply odds (free: no API calls)."""
    return await asyncio.to_thread(odds.best_bets)


@app.get("/api/apply-list")
async def apply_list():
    """Jobs the agent says are worth applying to, each compared with your current resume (free: no API calls)."""
    apps = await asyncio.to_thread(db.list_applications)
    resume = db.get_profile().get("resume") or ""
    out = []
    for a in apps:
        rep = a.get("report") or {}
        score = a.get("ghost_score")
        if score is None or a.get("status") in {"rejected", "ghosted", "offer"}:
            continue
        if rep.get("apply") == "Skip it" or score >= 50:
            continue
        out.append({
            "id": a["id"], "company": a.get("company"), "title": a.get("title"), "status": a.get("status"),
            "ghost_score": score, "apply": rep.get("apply"), "url": a.get("url"),
            "fit": (rep.get("fit") or {}).get("score"),
            "keywords": skills.match(rep.get("job") or {}, resume),
        })
    # Best bets first: least ghosty, then best keyword match.
    out.sort(key=lambda j: (j["ghost_score"], -((j["keywords"] or {}).get("score") or 0)))
    return {"has_resume": bool(resume.strip()), "jobs": out}


@app.get("/api/skill-gaps")
async def skill_gaps():
    reports = await asyncio.to_thread(db.list_reports)
    return skills.gaps_across_jobs(reports, db.get_profile().get("resume") or "")


@app.get("/api/companies")
async def companies():
    return await asyncio.to_thread(db.company_history)


@app.get("/api/profile")
async def get_profile():
    return await asyncio.to_thread(db.get_profile)


@app.put("/api/profile")
async def put_profile(body: ProfileIn):
    await asyncio.to_thread(db.set_profile, body.model_dump())
    return {"ok": True}


@app.post("/api/profile/resume-file")
async def upload_resume(file: UploadFile = File(...)):
    """Read a PDF / Word / text resume locally and save its text to your profile (free: no API calls)."""
    data = await file.read()
    try:
        text = await asyncio.to_thread(resume_files.extract_text, file.filename or "", data)
    except resume_files.ResumeFileError as e:
        raise HTTPException(400, str(e))
    # Keep the original file next to the database (used later by the ATS checker).
    ext = (file.filename or "resume").rsplit(".", 1)[-1].lower()
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    for old in config.DB_PATH.parent.glob("resume_upload.*"):
        old.unlink(missing_ok=True)
    (config.DB_PATH.parent / f"resume_upload.{ext}").write_bytes(data)
    await asyncio.to_thread(db.set_profile, {"resume": text, "resume_filename": file.filename or ""})
    return {"resume": text, "filename": file.filename, "chars": len(text)}


@app.get("/api/streak")
async def streak(tz_offset: int = 0):
    p = db.get_profile()
    times = await asyncio.to_thread(db.apply_times)
    return streaks.compute(times, tz_offset, int(p.get("daily_goal") or 1), p.get("motivation") or "both")


@app.post("/api/streak/external")
async def streak_external():
    await asyncio.to_thread(db.log_external_apply)
    return {"ok": True}


@app.delete("/api/streak/external")
async def streak_external_undo():
    return {"ok": await asyncio.to_thread(db.undo_last_external_apply)}


@app.get("/api/events")
async def events():
    return await asyncio.to_thread(db.list_events)


@app.post("/api/events/seen")
async def events_seen():
    await asyncio.to_thread(db.mark_events_seen)
    return {"ok": True}


@app.post("/api/daily")
async def run_daily():
    if config.PUBLIC and not config.DEMO_MODE:
        raise HTTPException(403, "The daily re-check is turned off on the public demo to protect credits. "
                                 "It runs on a schedule when you host GhostBusted yourself.")
    return {"notes": await daily.run(force=True)}
