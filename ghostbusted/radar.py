# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Response Radar: ghost scores that learn from what actually happened to your applications.

Every ghost-job tool guesses from the posting. This adjusts the guess with real outcomes:
if a company has ghosted you before, the score goes up; if it has replied to you, it comes down.
Pure Python on your own data: no API calls.
"""
from __future__ import annotations

from . import db


def adjustment(r: dict | None) -> tuple[int, str | None, str]:
    """Returns (points to add to the ghost score, plain-English finding, direction)."""
    if not r:
        return 0, None, "neutral"
    ghosted, replied = r["ghosted"], r["responded"]
    if ghosted == 0 and replied == 0:
        if r["pending"]:
            return 0, f"You have {r['pending']} application(s) here still waiting on a reply. No outcome yet.", "neutral"
        return 0, None, "neutral"
    # Each ghosting adds evidence; each reply removes it. Capped so one data point can't dominate.
    pts = max(-20, min(25, 12 * ghosted - 10 * replied))
    d = r.get("avg_reply_days")
    speed = "" if d is None else ", average reply in under a day" if d < 1 else f", average reply in {d} days"
    finding = f"Your own history: {replied} of {replied + ghosted} applications got a reply{speed}; {ghosted} ghosted you."
    return pts, finding, "ghost" if pts > 0 else "real" if pts < 0 else "neutral"


def apply(report: dict) -> dict:
    """Adjust a fresh report's ghost score with your Response Radar history for that company."""
    company = (report.get("job") or {}).get("company") or ""
    r = db.response_radar().get(db.norm_company(company))
    pts, finding, direction = adjustment(r)
    base = report.get("ghost_score") or 0
    report["radar"] = {**(r or {}), "adjustment": pts, "base_score": base} if r else None
    if finding:
        report.setdefault("signals", []).insert(0, {
            "name": "Your Response Radar", "finding": finding, "direction": direction,
            "weight": 3 if abs(pts) >= 12 else 2, "sources": []})
    if pts:
        new = max(0, min(100, base + pts))
        report["ghost_score"] = new
        # Keep the verdict label consistent with the adjusted score.
        report["verdict"] = "Likely ghost" if new >= 65 else "Proceed with caution" if new >= 40 else "Likely real"
        # ...and soften a recommendation that no longer fits the adjusted score.
        if new >= 65 and report.get("apply") == "Apply now":
            report["apply"] = "Apply, but don't wait on it"
        if new < 40 and report.get("apply") == "Skip it":
            report["apply"] = "Apply, but don't wait on it"
    return report
