# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""The always-on part. Run once a day (Nebius Serverless Job, cron, or the "Run daily check" button).

For every job you're tracking:
  - re-investigate it and alert you if it turned into a ghost (score jumped)
  - nudge you with a drafted follow-up email when it's been FOLLOWUP_DAYS since you applied
  - auto-mark it 'ghosted' after 30 days of silence

Usage:  python -m ghostbusted.daily
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from . import analyzer, config, db, radar

log = logging.getLogger("ghostbusted.daily")
ACTIVE = {"saved", "applied", "interviewing"}


async def _noop(_):
    return None


def _age_days(iso: str | None) -> float | None:
    if not iso:
        return None
    return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 86400


async def check_one(app: dict, profile: dict, force: bool) -> list[str]:
    notes = []
    if not force and (_age_days(app.get("last_checked")) or 99) < 0.9:
        return notes
    old = app.get("ghost_score") or 0
    try:
        full = db.get_application(app["id"])
        report, _ = await analyzer.analyze(None, full.get("posting_text") or app.get("url"), profile, _noop)
        report = radar.apply(report)
        db.save_application(report, app.get("url"), full.get("posting_text") or "", app_id=app["id"])
        new = report.get("ghost_score") or 0
        if new - old >= 15:
            msg = f"{app['company']} · {app['title']} went from {old} to {new} on the ghost meter."
            db.add_event(app["id"], "ghost_alert", msg, {"old": old, "new": new, "headline": report.get("headline")})
            notes.append(msg)
    except Exception as e:
        log.warning("recheck failed for %s: %s", app["id"], e)

    if app["status"] == "applied" and not app.get("followup_sent_at"):
        age = _age_days(app.get("applied_at")) or 0
        if age >= config.FOLLOWUP_DAYS and not db.has_event(app["id"], "followup_due"):
            draft = await analyzer.draft_followup(app, profile)
            msg = f"It's been {int(age)} days since you applied to {app['company']}. Here's a follow-up ready to send."
            db.add_event(app["id"], "followup_due", msg, {"draft": draft})
            notes.append(msg)
        if age >= 30:
            db.update_status(app["id"], "ghosted")
            db.add_event(app["id"], "auto_ghosted", f"No word from {app['company']} in 30 days. Marked as ghosted.")
            notes.append(f"Auto-ghosted {app['company']}")
    return notes


async def run(force: bool = False) -> list[str]:
    profile = db.get_profile()
    apps = [a for a in db.list_applications() if a["status"] in ACTIVE]
    sem = asyncio.Semaphore(4)  # keep Tavily/Token Factory rate limits happy

    async def guarded(a):
        async with sem:
            return await check_one(a, profile, force)

    results = await asyncio.gather(*(guarded(a) for a in apps))
    notes = [n for r in results for n in r]
    log.info("daily check: %d jobs, %d notes", len(apps), len(notes))
    return notes


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for n in asyncio.run(run(force=True)):
        print("•", n)
