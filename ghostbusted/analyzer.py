# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""The ghost-job investigation pipeline.

  1. Read the posting       (Tavily Extract)                    -> raw text
  2. Parse it               (Nemotron Nano, structured JSON)    -> company, title, salary, date...
  3. Investigate in parallel (5 Tavily searches)                 -> evidence with sources
  4. Red-flag heuristics    (deterministic, instant)            -> posting-text signals
  5. Verdict                (Nemotron Ultra, reasoning)         -> ghost score + receipts + fit + advice

Every step emits a progress event so the UI can show the investigation live.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime
from typing import Awaitable, Callable

from . import config, demo

Emit = Callable[[dict], Awaitable[None]]

PARSE_SYSTEM = """You extract structured data from job postings. Return ONLY JSON with keys:
company (string), title (string), location (string), posted_date (YYYY-MM-DD or null),
salary (string or null), seniority (string), employment_type (string),
requirements (list of up to 8 short strings), summary (one sentence),
required_skills (list of up to 15 short keywords the posting says are required: tools, languages, frameworks,
platforms, certifications, methods, e.g. "Python", "SQL", "Tableau", "A/B testing", "AWS"),
preferred_skills (list of up to 10 short keywords marked nice-to-have, preferred, or bonus).
Keywords must be 1-4 words, use the posting's own wording, no years-of-experience or soft fluff like "team player".
If a field is not present, use null (or [] for lists). Do not invent values."""

VERDICT_SYSTEM = """You are GhostBusted, an investigator that decides whether a job posting is a "ghost job"
(posted with no real intent to hire soon: evergreen talent pools, reposted roles, hiring freezes, roles kept up for optics).

You get: the parsed posting, red flags found in the posting text, web evidence gathered by search (each item has a URL),
and optionally the candidate's resume.

Rules:
- Base every claim on the evidence. If evidence is thin, say so and keep the score near the middle (40-60).
- Cite only URLs that appear in the evidence. Never invent sources.
- Evidence about a different company with a similar name does not count.
- ghost_score: 0 = clearly real and actively hiring, 100 = almost certainly a ghost.
- headline: one punchy, plain-English line a Gen Z job seeker would screenshot (no emojis, max 14 words).

Return ONLY JSON:
{
 "ghost_score": int,
 "verdict": "Likely real" | "Proceed with caution" | "Likely ghost",
 "confidence": "low" | "medium" | "high",
 "headline": str,
 "signals": [ {"name": str, "finding": str, "direction": "ghost" | "real" | "neutral", "weight": 1-3, "sources": [url]} ],
 "fit": {"score": int 0-100 or null, "strengths": [str], "gaps": [str]},
 "advice": [str, max 4 concrete next steps],
 "apply": "Apply now" | "Apply, but don't wait on it" | "Skip it"
}"""

RED_FLAG_PATTERNS = [
    (r"talent (pool|community|network)", "Talent-pool language", "Posting says it is building a talent pool rather than filling a role."),
    (r"future (opportunit|opening|role)", "Future-opportunity language", "Mentions future openings, not a current one."),
    (r"evergreen", "Evergreen requisition", "Explicitly marked as an evergreen posting."),
    (r"always (hiring|looking|accepting)", "Always-hiring language", "Says they are always hiring."),
    (r"pipeline", "Pipeline language", "Talks about building a candidate pipeline."),
    (r"no (immediate|current) opening", "No current opening", "States there is no immediate opening."),
]


def red_flags(text: str, parsed: dict) -> list[dict]:
    t = (text or "").lower()
    flags = [{"name": n, "finding": f} for p, n, f in RED_FLAG_PATTERNS if re.search(p, t)]
    if not parsed.get("salary"):
        flags.append({"name": "No salary listed", "finding": "No pay range in the posting."})
    pd = parsed.get("posted_date")
    if pd:
        try:
            age = (date.today() - datetime.strptime(pd[:10], "%Y-%m-%d").date()).days
            if age > 45:
                flags.append({"name": "Stale posting", "finding": f"Posted {age} days ago."})
        except ValueError:
            pass
    if len(parsed.get("requirements") or []) >= 8 and (parsed.get("seniority") or "").lower() in {"entry", "junior", "entry level", "entry-level"}:
        flags.append({"name": "Unrealistic entry-level asks", "finding": "Long requirement list for an entry-level role."})
    return flags


def _clean_sources(report: dict, evidence: dict) -> dict:
    """Drop any URL the model cited that wasn't in our evidence."""
    allowed = {r["url"] for v in evidence.values() for r in v.get("results", [])}
    for s in report.get("signals", []):
        s["sources"] = [u for u in (s.get("sources") or []) if u in allowed][:3]
    try:
        report["ghost_score"] = max(0, min(100, int(report.get("ghost_score", 50))))
    except (TypeError, ValueError):
        report["ghost_score"] = 50
    return report


async def analyze(url: str | None, text: str | None, profile: dict, emit: Emit) -> tuple[dict, str]:
    """Returns (report, posting_text)."""
    if config.DEMO_MODE:
        return await demo.analyze(url, text, profile, emit)

    from . import llm, search  # imported lazily so demo mode needs no keys

    # 1. read
    await emit({"type": "step", "id": "read", "status": "running", "label": "Reading the posting"})
    posting = (text or "").strip()
    if url and not posting:
        posting = await search.extract_page(url)
    if not posting:
        raise ValueError("Couldn't read that posting. Paste the job description text instead.")
    await emit({"type": "step", "id": "read", "status": "done", "label": "Reading the posting",
                "detail": f"{len(posting):,} characters via Tavily Extract" if url and not text else "Pasted text"})

    # 2. parse (Nano)
    await emit({"type": "step", "id": "parse", "status": "running", "label": "Parsing with Nemotron Nano"})
    parsed, parse_model = await llm.chat_json("nano", PARSE_SYSTEM, posting[:12000], max_tokens=4000)

    def _usable(p: dict) -> bool:
        ok = lambda v: isinstance(v, str) and len(v.strip(" .-")) > 1
        return ok(p.get("title")) and (ok(p.get("company")) or bool(p.get("required_skills")))

    if not _usable(parsed):  # Nano came back empty or cut off: ask Nemotron Super instead
        try:
            parsed, parse_model = await llm.chat_json("super", PARSE_SYSTEM, posting[:12000], max_tokens=4000)
        except Exception:
            pass
    clean = lambda v, d: v if isinstance(v, str) and len(v.strip(" .-")) > 1 else d
    company, title = clean(parsed.get("company"), "Unknown company"), clean(parsed.get("title"), "Unknown role")
    parsed["company"], parsed["title"] = company, title
    await emit({"type": "step", "id": "parse", "status": "done", "label": "Parsing with Nemotron Nano",
                "detail": f"{title} at {company}", "model": parse_model})

    # 3. investigate (Tavily, parallel) + 4. heuristics
    async def on_done(key, data):
        await emit({"type": "step", "id": f"search_{key}", "status": "done", "label": data["label"],
                    "detail": f"{len(data['results'])} sources"})

    for key, spec in search.investigations(company, title).items():
        await emit({"type": "step", "id": f"search_{key}", "status": "running", "label": spec["label"]})
    evidence = await search.investigate(company, title, on_done)
    flags = red_flags(posting, parsed)

    # 5. verdict (Ultra)
    await emit({"type": "step", "id": "verdict", "status": "running", "label": "Weighing the evidence with Nemotron Ultra"})
    resume = (profile.get("resume") or "").strip()
    payload = {
        "today": date.today().isoformat(),
        "posting": parsed,
        "posting_red_flags": flags,
        "evidence": evidence,
        "candidate_resume": resume[:6000] or None,
        "candidate_goals": profile.get("goals") or None,
    }
    report, verdict_model = await llm.chat_json("ultra", VERDICT_SYSTEM, json.dumps(payload, ensure_ascii=False),
                                                max_tokens=2500)
    report = _clean_sources(report, evidence)
    report["job"] = parsed
    report["red_flags"] = flags
    report["evidence"] = evidence
    report["models"] = {"parse": parse_model, "verdict": verdict_model}
    report["checked_at"] = datetime.now().isoformat(timespec="seconds")
    await emit({"type": "step", "id": "verdict", "status": "done", "label": "Weighing the evidence with Nemotron Ultra",
                "model": verdict_model})
    return report, posting


async def draft_followup(app: dict, profile: dict) -> str:
    if config.DEMO_MODE:
        return demo.followup(app)
    from . import llm

    job = (app.get("report") or {}).get("job", {})
    prompt = json.dumps({"company": app.get("company"), "role": app.get("title"), "applied_at": app.get("applied_at"),
                         "job_summary": job.get("summary"), "resume": (profile.get("resume") or "")[:3000]})
    text, _ = await llm.chat("super", "Write a short, warm, specific follow-up email (under 120 words) from a job "
                             "applicant to a recruiter. Include a subject line. No placeholders except [Recruiter name].",
                             prompt, max_tokens=500, temperature=0.5)
    return text
