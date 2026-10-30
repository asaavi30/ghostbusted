# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Best bets: rank the jobs you haven't applied to yet by your odds of getting a reply.

Combines four signals no single tool combines:
  real    how likely the job is real          (1 - ghost score)
  fresh   how new the posting is              (early applicants get read)
  fit     how well your resume matches        (keyword match)
  company whether this company replies to YOU (Response Radar, your real outcomes)

The result is a relative 0-100 "reply odds" score, not a probability. Every factor is shown so you can see why.
Pure Python, no API calls.
"""
from __future__ import annotations

from datetime import date, datetime

from . import db, skills


def _posting_age(job: dict) -> int | None:
    pd = (job or {}).get("posted_date")
    if not pd:
        return None
    try:
        return max(0, (date.today() - datetime.strptime(str(pd)[:10], "%Y-%m-%d").date()).days)
    except ValueError:
        return None


def _fresh_factor(age: int | None) -> tuple[float, str]:
    if age is None:
        return 0.8, "Posting date unknown"
    if age <= 3:
        return 1.0, f"Posted {age} day{'s' if age != 1 else ''} ago: you'd be an early applicant"
    if age <= 7:
        return 0.9, f"Posted {age} days ago: still fresh"
    if age <= 14:
        return 0.75, f"Posted {age} days ago: apply soon"
    if age <= 30:
        return 0.55, f"Posted {age} days ago: getting stale"
    return 0.35, f"Posted {age} days ago: very stale"


def score(app: dict, resume: str, radar: dict[str, dict]) -> dict:
    rep = app.get("report") or {}
    job = rep.get("job") or {}
    ghost = app.get("ghost_score")
    real = 1 - (ghost if ghost is not None else 50) / 100

    age = _posting_age(job)
    fresh, fresh_note = _fresh_factor(age)

    kw = skills.match(job, resume) if resume.strip() else None
    if kw and kw.get("score") is not None:
        fit_pct = kw["score"]
        fit = 0.4 + 0.6 * fit_pct / 100
        fit_note = f"Keyword match {fit_pct}%"
    elif not resume.strip():
        fit_pct, fit, fit_note = None, 0.7, "Add your resume in Profile to score fit"
    else:
        fit_pct, fit, fit_note = None, 0.7, "No skills found in this posting. Paste the full job text and check it again"

    r = radar.get(db.norm_company(app.get("company")))
    decided = (r["responded"] + r["ghosted"]) if r else 0
    if decided:
        rate = r["responded"] / decided
        company = min(1.5, 0.5 + rate)
        company_note = f"This company replied to {r['responded']} of your {decided} applications"
    else:
        rate, company, company_note = None, 1.0, "No history with this company yet"

    odds = round(min(99, 100 * real * fresh * fit * company))
    factors = [
        {"key": "real", "label": "Real job", "value": round(real * 100), "note": f"Ghost score {ghost}"},
        {"key": "fresh", "label": "Freshness", "value": round(fresh * 100), "note": fresh_note},
        {"key": "fit", "label": "Your fit", "value": round(fit * 100), "note": fit_note, "neutral": fit_pct is None},
        {"key": "company", "label": "Company replies", "value": round(min(company, 1.0) * 100), "note": company_note,
         "neutral": not decided},
    ]
    # Plain-English reason: what's going for it, then the biggest drag and how to fix it.
    # Factors with no information (no company history, no resume) are neutral: never "strongest" or "worst".
    known = [f for f in factors if not (f["key"] == "company" and not decided) and not (f["key"] == "fit" and fit_pct is None)]
    pros = {
        "real": f"likely a real opening (ghost score {ghost})",
        "fresh": fresh_note.split(":")[0].lower() + ", so you'd be early" if age is not None and age <= 7 else None,
        "fit": f"strong keyword match ({fit_pct}%)" if fit_pct is not None else None,
        "company": "this company has replied to you before" if decided and rate and rate > 0 else None,
    }
    good = [pros[f["key"]] for f in sorted(known, key=lambda f: -f["value"]) if f["value"] >= 70 and pros.get(f["key"])]
    reason = ("Going for it: " + "; ".join(good[:2]) + ".") if good else "Nothing stands out in its favor."
    worst = min(known, key=lambda f: f["value"]) if known else None
    if worst and worst["value"] < 70:
        if worst["key"] == "fit" and kw and kw["missing_required"]:
            reason += f" Biggest drag: your fit. Add {', '.join(kw['missing_required'][:3])} if you really have them."
        elif worst["key"] == "fit":
            reason += " Biggest drag: your fit is low for this one."
        elif worst["key"] == "fresh":
            reason += f" Biggest drag: it's been up {age} days, so apply today or skip it."
        elif worst["key"] == "company":
            reason += " Biggest drag: this company has ghosted you before."
        elif worst["key"] == "real":
            reason += f" Biggest drag: high ghost-job risk (score {ghost})."
    tier = "High" if odds >= 55 else "Medium" if odds >= 30 else "Low"
    return {
        "id": app["id"], "company": app.get("company") or "Unknown company",
        "title": app.get("title") if len((app.get("title") or "").strip(" .")) > 1 else "Unreadable posting",
        "url": app.get("url"),
        "status": app.get("status"), "ghost_score": ghost, "odds": odds, "tier": tier,
        "factors": factors, "reason": reason, "posting_age_days": age,
        "missing_required": (kw or {}).get("missing_required", [])[:5],
    }


def best_bets() -> dict:
    resume = db.get_profile().get("resume") or ""
    radar = db.response_radar()
    apps = db.list_applications()
    ranked = sorted((score(a, resume, radar) for a in apps if a.get("status") == "saved"),
                    key=lambda x: -x["odds"])
    # Calibration: once you have outcomes, check whether high-odds jobs really replied more often.
    calib = {"High": [0, 0], "Medium": [0, 0], "Low": [0, 0]}  # [replied, decided]
    for a in apps:
        if a.get("status") == "saved":
            continue
        if a["status"] in db.RESPONDED or a["status"] == "ghosted":
            t = score(a, resume, {})["tier"]  # score without company history, to avoid grading itself
            calib[t][1] += 1
            calib[t][0] += 1 if a["status"] in db.RESPONDED else 0
    calibration = {t: {"replied": v[0], "decided": v[1], "rate": round(100 * v[0] / v[1]) if v[1] else None}
                   for t, v in calib.items()}
    return {
        "has_resume": bool(resume.strip()),
        "daily_goal": int(db.get_profile().get("daily_goal") or 1),
        "jobs": ranked,
        "calibration": calibration,
        "decided_total": sum(v[1] for v in calib.values()),
    }
