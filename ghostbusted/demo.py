# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Demo mode: realistic canned responses so the app runs with no API keys.
Companies here are fictional. Real runs go through Tavily + Nemotron (see analyzer.py)."""
from __future__ import annotations

import asyncio
import copy
from datetime import date, datetime, timedelta

GHOST_POSTING = """Quillery Analytics - Junior Data Analyst (Remote, US)
We're always looking for passionate analysts to join our talent community! While there may be no immediate opening,
we're building a pipeline for future opportunities across our data org.
Requirements: SQL, Python, Tableau, dbt, Airflow, Spark, AWS, 3+ years experience, stakeholder management, A/B testing.
Posted: """ + (date.today() - timedelta(days=96)).isoformat()

REAL_POSTING = """Tandemvolt Robotics - Software Engineer, New Grad (Austin, TX)
Pay: $118,000 - $135,000. Start date: January 2027. Team: Fleet Autonomy.
You'll ship code to our warehouse robot fleet in your first month. Requirements: Python or C++, data structures, Linux.
Posted: """ + (date.today() - timedelta(days=6)).isoformat()


def _ev(label, results, answer=None):
    return {"label": label, "answer": answer, "results": results}


GHOST = {
    "job": {"company": "Quillery Analytics", "title": "Junior Data Analyst", "location": "Remote, US",
            "posted_date": (date.today() - timedelta(days=96)).isoformat(), "salary": None, "seniority": "entry level",
            "employment_type": "Full-time",
            "requirements": ["SQL", "Python", "Tableau", "dbt", "Airflow", "Spark", "AWS", "3+ years experience"],
            "required_skills": ["SQL", "Python", "Tableau", "dbt", "Airflow", "Spark", "AWS"],
            "preferred_skills": ["A/B testing", "Looker"],
            "summary": "Entry-level analyst role framed as building a talent community for future openings."},
    "evidence": {
        "layoffs": _ev("Layoffs & hiring freezes", [{"title": "Quillery Analytics cuts 18% of staff, pauses hiring", "url": "https://example.com/demo/quillery-layoffs", "snippet": "The company announced an 18% reduction and a hiring pause through Q1.", "date": "2026-09-14"}]),
        "reposts": _ev("Repost history", [{"title": "Junior Data Analyst - Quillery Analytics (reposted)", "url": "https://example.com/demo/quillery-repost-1", "snippet": "Same posting seen in June, August, September and October.", "date": None}]),
        "applicant_reports": _ev("Applicant reports", [{"title": "r/jobs: Applied to Quillery 3 times, never heard back", "url": "https://example.com/demo/reddit-quillery", "snippet": "Thread with 40+ comments reporting no response from this listing.", "date": "2026-10-02"}]),
        "careers_page": _ev("Official careers page", [{"title": "Quillery Analytics Careers", "url": "https://example.com/demo/quillery-careers", "snippet": "Careers page lists 2 open roles, neither is Junior Data Analyst.", "date": None}]),
        "company_health": _ev("Company health", [{"title": "Quillery Analytics misses revenue targets", "url": "https://example.com/demo/quillery-revenue", "snippet": "Revenue fell short of guidance for the second quarter in a row.", "date": "2026-08-20"}]),
    },
    "ghost_score": 87, "verdict": "Likely ghost", "confidence": "high",
    "headline": "Reposted four times, hiring frozen, and nobody's heard back. It's a ghost.",
    "signals": [
        {"name": "Hiring freeze", "finding": "Company announced an 18% layoff and a hiring pause in September.", "direction": "ghost", "weight": 3, "sources": ["https://example.com/demo/quillery-layoffs"]},
        {"name": "Serial reposting", "finding": "Identical posting reappeared in June, August, September and October.", "direction": "ghost", "weight": 3, "sources": ["https://example.com/demo/quillery-repost-1"]},
        {"name": "Applicants ghosted", "finding": "40+ applicants on Reddit report zero response to this listing.", "direction": "ghost", "weight": 2, "sources": ["https://example.com/demo/reddit-quillery"]},
        {"name": "Missing from careers page", "finding": "Role isn't listed on the company's own careers site.", "direction": "ghost", "weight": 2, "sources": ["https://example.com/demo/quillery-careers"]},
        {"name": "Talent-pool language", "finding": "Posting itself says there may be no immediate opening.", "direction": "ghost", "weight": 2, "sources": []},
    ],
    "fit": {"score": 64, "strengths": ["SQL and Python match", "Tableau dashboard projects"], "gaps": ["No dbt or Airflow", "Asks for 3+ years on an entry-level title"]},
    "advice": ["Don't spend time tailoring for this one.", "If you still apply, use a 2-minute quick apply.",
               "Look for analyst roles posted in the last 14 days with a salary range.",
               "Message a Quillery data team member on LinkedIn to ask if the role is actually open."],
    "apply": "Skip it",
}

REAL = {
    "job": {"company": "Tandemvolt Robotics", "title": "Software Engineer, New Grad", "location": "Austin, TX",
            "posted_date": (date.today() - timedelta(days=6)).isoformat(), "salary": "$118,000 - $135,000",
            "seniority": "entry level", "employment_type": "Full-time",
            "requirements": ["Python or C++", "Data structures", "Linux"],
            "required_skills": ["Python", "C++", "Data structures", "Linux"],
            "preferred_skills": ["ROS", "Kubernetes", "Git"],
            "summary": "New-grad engineer on the fleet autonomy team with a set start date."},
    "evidence": {
        "layoffs": _ev("Layoffs & hiring freezes", []),
        "reposts": _ev("Repost history", [{"title": "Tandemvolt Robotics New Grad SWE", "url": "https://example.com/demo/tandemvolt-post", "snippet": "First seen 6 days ago; no earlier copies found.", "date": None}]),
        "applicant_reports": _ev("Applicant reports", [{"title": "Tandemvolt interview experience - got a call in 5 days", "url": "https://example.com/demo/tandemvolt-interview", "snippet": "Recruiter screen within a week, onsite two weeks later.", "date": "2026-10-11"}]),
        "careers_page": _ev("Official careers page", [{"title": "Tandemvolt Careers - Software Engineer, New Grad", "url": "https://example.com/demo/tandemvolt-careers", "snippet": "Role listed on official careers page with team and start date.", "date": None}]),
        "company_health": _ev("Company health", [{"title": "Tandemvolt Robotics raises $60M Series C", "url": "https://example.com/demo/tandemvolt-funding", "snippet": "Funding to double the engineering team in 2027.", "date": "2026-09-30"}]),
    },
    "ghost_score": 12, "verdict": "Likely real", "confidence": "high",
    "headline": "Fresh posting, real salary, new funding. This one's hiring for real.",
    "signals": [
        {"name": "Fresh funding", "finding": "Raised a $60M Series C to double engineering in 2027.", "direction": "real", "weight": 3, "sources": ["https://example.com/demo/tandemvolt-funding"]},
        {"name": "On the careers page", "finding": "Listed on the official site with team and start date.", "direction": "real", "weight": 2, "sources": ["https://example.com/demo/tandemvolt-careers"]},
        {"name": "Recruiters respond", "finding": "Recent applicants report a recruiter screen within a week.", "direction": "real", "weight": 2, "sources": ["https://example.com/demo/tandemvolt-interview"]},
        {"name": "Salary and start date listed", "finding": "Clear pay range and a January 2027 start.", "direction": "real", "weight": 2, "sources": []},
    ],
    "fit": {"score": 81, "strengths": ["Python projects", "Linux experience"], "gaps": ["No C++ shown"]},
    "advice": ["Apply this week; the posting is 6 days old.", "Lead with your robotics or systems project.",
               "Mention the fleet autonomy team by name in your note.", "Follow up in 7 days if no response."],
    "apply": "Apply now",
}


async def analyze(url, text, profile, emit):
    raw = f"{url or ''} {text or ''}".lower()
    is_real = "tandemvolt" in raw or "real" in raw.split()
    report = copy.deepcopy(REAL if is_real else GHOST)
    posting = REAL_POSTING if is_real else GHOST_POSTING
    if not (profile.get("resume") or "").strip():
        report["fit"] = {"score": None, "strengths": [], "gaps": []}

    async def step(id_, label, detail=None, model=None, wait=0.35):
        await emit({"type": "step", "id": id_, "status": "running", "label": label})
        await asyncio.sleep(wait)
        await emit({"type": "step", "id": id_, "status": "done", "label": label, "detail": detail, "model": model})

    await step("read", "Reading the posting", "Demo posting")
    await step("parse", "Parsing with Nemotron Nano", f"{report['job']['title']} at {report['job']['company']}",
               "demo:nemotron-nano")
    keys = list(report["evidence"].keys())
    for k in keys:
        await emit({"type": "step", "id": f"search_{k}", "status": "running", "label": report["evidence"][k]["label"]})
    for k in keys:
        await asyncio.sleep(0.25)
        await emit({"type": "step", "id": f"search_{k}", "status": "done", "label": report["evidence"][k]["label"],
                    "detail": f"{len(report['evidence'][k]['results'])} sources"})
    await step("verdict", "Weighing the evidence with Nemotron Ultra", None, "demo:nemotron-ultra", wait=0.8)

    report["red_flags"] = []
    report["models"] = {"parse": "demo:nemotron-nano", "verdict": "demo:nemotron-ultra"}
    report["checked_at"] = datetime.now().isoformat(timespec="seconds")
    report["demo"] = True
    return report, posting


def followup(app):
    return (f"Subject: Following up on my {app.get('title')} application\n\n"
            f"Hi [Recruiter name],\n\nI applied for the {app.get('title')} role at {app.get('company')} last week and "
            "wanted to share how excited I am about it. I'd love to bring my experience with Python and data projects "
            "to the team. Is there anything else I can send to help with your review?\n\nThanks so much,\n[Your name]")
