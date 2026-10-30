# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Persistent memory: your profile, every job you've checked, score history, nudges.

SQLite in WAL mode: zero setup, fast, and the file is yours.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

from . import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT, company TEXT, title TEXT, location TEXT,
    status TEXT DEFAULT 'saved',            -- saved | applied | interviewing | offer | rejected | ghosted
    ghost_score INTEGER, verdict TEXT, headline TEXT,
    report TEXT, posting_text TEXT,
    score_history TEXT DEFAULT '[]',
    created_at TEXT, applied_at TEXT, last_checked TEXT, followup_sent_at TEXT
);
CREATE TABLE IF NOT EXISTS status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, app_id INTEGER, status TEXT, at TEXT
);
CREATE TABLE IF NOT EXISTS apply_log (       -- one row per application you sent (streaks)
    id INTEGER PRIMARY KEY AUTOINCREMENT, app_id INTEGER, note TEXT, at TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER, kind TEXT, message TEXT, payload TEXT,
    created_at TEXT, seen INTEGER DEFAULT 0
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
        # Older databases: count jobs you'd already marked as applied toward your streak history.
        _conn.execute("""INSERT INTO apply_log(app_id, note, at)
                         SELECT id, NULL, applied_at FROM applications
                         WHERE applied_at IS NOT NULL
                           AND id NOT IN (SELECT app_id FROM apply_log WHERE app_id IS NOT NULL)""")
        _conn.commit()
    return _conn


def _row(r: sqlite3.Row | None) -> dict | None:
    if r is None:
        return None
    d = dict(r)
    for k in ("report", "score_history", "payload"):
        if k in d and d[k]:
            try:
                d[k] = json.loads(d[k])
            except Exception:
                pass
    return d


# ---------- profile ----------
def get_profile() -> dict[str, str]:
    with _lock:
        rows = conn().execute("SELECT key, value FROM profile").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_profile(data: dict[str, str]) -> None:
    with _lock, conn():
        for k, v in data.items():
            conn().execute("INSERT INTO profile(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (k, v or ""))


# ---------- applications ----------
def save_application(report: dict, url: str | None, posting_text: str, app_id: int | None = None) -> int:
    job = report.get("job", {})
    entry = {"at": now(), "score": report.get("ghost_score")}
    with _lock, conn():
        c = conn()
        if not app_id:  # re-checking a job you've seen before updates it instead of duplicating it
            hit = (c.execute("SELECT id FROM applications WHERE url=?", (url,)).fetchone() if url else None) or \
                  c.execute("SELECT id FROM applications WHERE lower(company)=lower(?) AND lower(title)=lower(?)",
                            (job.get("company") or "", job.get("title") or "")).fetchone()
            app_id = hit["id"] if hit else None
        if app_id:
            old = c.execute("SELECT score_history FROM applications WHERE id=?", (app_id,)).fetchone()
            hist = json.loads(old["score_history"]) if old and old["score_history"] else []
            hist.append(entry)
            c.execute("""UPDATE applications SET ghost_score=?, verdict=?, headline=?, report=?, score_history=?,
                         last_checked=? WHERE id=?""",
                      (report.get("ghost_score"), report.get("verdict"), report.get("headline"), json.dumps(report),
                       json.dumps(hist), now(), app_id))
            return app_id
        cur = c.execute(
            """INSERT INTO applications(url, company, title, location, ghost_score, verdict, headline, report,
                   posting_text, score_history, created_at, last_checked)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (url, job.get("company"), job.get("title"), job.get("location"), report.get("ghost_score"),
             report.get("verdict"), report.get("headline"), json.dumps(report), posting_text,
             json.dumps([entry]), now(), now()))
        return cur.lastrowid


def list_applications() -> list[dict]:
    with _lock:
        rows = conn().execute("SELECT * FROM applications ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = _row(r)
        d.pop("posting_text", None)
        out.append(d)
    return out


def list_reports() -> list[dict]:
    with _lock:
        rows = conn().execute("SELECT report FROM applications").fetchall()
    out = []
    for r in rows:
        try:
            out.append(json.loads(r["report"]) if r["report"] else {})
        except Exception:
            pass
    return out


def get_application(app_id: int) -> dict | None:
    with _lock:
        return _row(conn().execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone())


APPLIED_OR_LATER = {"applied", "interviewing", "offer", "rejected", "ghosted"}
RESPONDED = {"interviewing", "offer", "rejected"}  # any reply from the company counts, even a rejection


def update_status(app_id: int, status: str) -> None:
    with _lock, conn():
        c = conn()
        row = c.execute("SELECT status, applied_at FROM applications WHERE id=?", (app_id,)).fetchone()
        if not row or row["status"] == status:
            return
        t = now()
        c.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
        # Moving to any applied-or-later status means you applied: record it once (feeds streaks + radar).
        if status in APPLIED_OR_LATER and not row["applied_at"]:
            c.execute("UPDATE applications SET applied_at=? WHERE id=?", (t, app_id))
            c.execute("INSERT INTO apply_log(app_id, note, at) VALUES(?,?,?)", (app_id, None, t))
        c.execute("INSERT INTO status_log(app_id, status, at) VALUES(?,?,?)", (app_id, status, t))


# ---------- streaks ----------
def log_external_apply() -> None:
    """An application you sent somewhere GhostBusted didn't check (still counts for your streak)."""
    with _lock, conn():
        conn().execute("INSERT INTO apply_log(app_id, note, at) VALUES(NULL, 'external', ?)", (now(),))


def undo_last_external_apply() -> bool:
    with _lock, conn():
        r = conn().execute("SELECT id FROM apply_log WHERE note='external' ORDER BY id DESC LIMIT 1").fetchone()
        if r:
            conn().execute("DELETE FROM apply_log WHERE id=?", (r["id"],))
        return bool(r)


def apply_times() -> list[str]:
    with _lock:
        return [r["at"] for r in conn().execute("SELECT at FROM apply_log ORDER BY at").fetchall()]


# ---------- Response Radar: what actually happened after you applied ----------
def response_radar() -> dict[str, dict]:
    """Per company: how many applications got a reply, how many ghosted you, and how fast replies came."""
    with _lock:
        apps = conn().execute("SELECT id, company, status, applied_at FROM applications WHERE applied_at IS NOT NULL").fetchall()
        logs = conn().execute("SELECT app_id, status, at FROM status_log ORDER BY at").fetchall()
    first_reply: dict[int, str] = {}
    for l in logs:
        if l["status"] in RESPONDED and l["app_id"] not in first_reply:
            first_reply[l["app_id"]] = l["at"]
    out: dict[str, dict] = {}
    for a in apps:
        key = norm_company(a["company"])
        if not key:
            continue
        r = out.setdefault(key, {"applied": 0, "responded": 0, "ghosted": 0, "pending": 0, "_days": []})
        r["applied"] += 1
        if a["id"] in first_reply or a["status"] in RESPONDED:
            r["responded"] += 1
            if a["id"] in first_reply:
                d = (datetime.fromisoformat(first_reply[a["id"]]) - datetime.fromisoformat(a["applied_at"])).total_seconds() / 86400
                r["_days"].append(max(0.0, d))
        elif a["status"] == "ghosted":
            r["ghosted"] += 1
        else:
            r["pending"] += 1
    for r in out.values():
        days = r.pop("_days")
        decided = r["responded"] + r["ghosted"]
        r["response_rate"] = round(100 * r["responded"] / decided) if decided else None
        r["avg_reply_days"] = round(sum(days) / len(days), 1) if days else None
    return out


def mark_followup_sent(app_id: int) -> None:
    with _lock, conn():
        conn().execute("UPDATE applications SET followup_sent_at=? WHERE id=?", (now(), app_id))


def delete_application(app_id: int) -> None:
    """Deletes the job. Its entry in your streak history stays (you really did apply)."""
    with _lock, conn():
        conn().execute("DELETE FROM applications WHERE id=?", (app_id,))
        conn().execute("DELETE FROM events WHERE app_id=?", (app_id,))
        conn().execute("DELETE FROM status_log WHERE app_id=?", (app_id,))
        conn().execute("UPDATE apply_log SET app_id=NULL WHERE app_id=?", (app_id,))


# ---------- company ghost history (pure SQL/Python, no API calls) ----------
_SUFFIX = re.compile(r"[,.]?\s+(inc|inc\.|llc|ltd|corp|corporation|co|company|gmbh|plc)\.?$", re.I)


def norm_company(name: str | None) -> str:
    n = (name or "").strip()
    n = _SUFFIX.sub("", n).strip(" ,.")
    return n.lower()


def company_history(only: str | None = None) -> list[dict]:
    """Group every job you've checked by company: average ghost score, counts, and the jobs themselves."""
    with _lock:
        rows = conn().execute(
            "SELECT id, company, title, status, ghost_score, verdict, last_checked FROM applications").fetchall()
    groups: dict[str, dict] = {}
    for r in rows:
        key = norm_company(r["company"])
        if not key or (only is not None and key != norm_company(only)):
            continue
        g = groups.setdefault(key, {"company": r["company"], "jobs": []})
        g["jobs"].append(dict(r))
    out = []
    for g in groups.values():
        scores = [j["ghost_score"] for j in g["jobs"] if j["ghost_score"] is not None]
        g["jobs"].sort(key=lambda j: j["last_checked"] or "", reverse=True)
        avg = round(sum(scores) / len(scores)) if scores else None
        out.append({
            "company": g["company"],
            "jobs_checked": len(g["jobs"]),
            "avg_score": avg,
            "max_score": max(scores) if scores else None,
            "ghost_count": sum(s >= 65 for s in scores),
            "real_count": sum(s < 40 for s in scores),
            "ghosted_you": sum(j["status"] == "ghosted" for j in g["jobs"]),
            "last_checked": g["jobs"][0]["last_checked"],
            "rating": None if avg is None else ("Ghost factory" if avg >= 65 else "Mixed signals" if avg >= 40 else "Hires for real"),
            "jobs": g["jobs"],
        })
    radar = response_radar()
    for c in out:
        c["radar"] = radar.get(norm_company(c["company"]))
    out.sort(key=lambda c: (c["avg_score"] is None, -(c["avg_score"] or 0)))
    return out


# ---------- events (nudges / alerts) ----------
def add_event(app_id: int, kind: str, message: str, payload: dict | None = None) -> None:
    with _lock, conn():
        conn().execute("INSERT INTO events(app_id, kind, message, payload, created_at) VALUES(?,?,?,?,?)",
                       (app_id, kind, message, json.dumps(payload or {}), now()))


def list_events(unseen_only: bool = False) -> list[dict]:
    q = "SELECT * FROM events" + (" WHERE seen=0" if unseen_only else "") + " ORDER BY created_at DESC LIMIT 50"
    with _lock:
        return [_row(r) for r in conn().execute(q).fetchall()]


def mark_events_seen() -> None:
    with _lock, conn():
        conn().execute("UPDATE events SET seen=1")


def has_event(app_id: int, kind: str) -> bool:
    with _lock:
        return conn().execute("SELECT 1 FROM events WHERE app_id=? AND kind=?", (app_id, kind)).fetchone() is not None
