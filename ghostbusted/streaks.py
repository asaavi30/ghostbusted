# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Application streaks + motivation. Pure Python, no API calls (free).

A day counts toward your streak when you log at least one application that day (in your local time).
Quotes are limited to ones with well-documented sources, always credited. Everything else is original.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from datetime import date, datetime, timedelta, timezone

# Only short quotes with a solid, documented source, always credited. (Many famous "quotes" online are
# misattributed.) All are public domain except the Gretzky line, a single short sentence from an interview.
QUOTES = [
    {"text": "You miss 100% of the shots you don't take.", "author": "Wayne Gretzky", "source": "The Hockey News, 1983"},
    {"text": "Little strokes fell great oaks.", "author": "Benjamin Franklin", "source": "Poor Richard's Almanack, 1750"},
    {"text": "Hope is a good breakfast, but it is a bad supper.", "author": "Francis Bacon", "source": "Apophthegms, 1624"},
    {"text": "I am not afraid of storms, for I am learning how to sail my ship.", "author": "Louisa May Alcott", "source": "Little Women, 1868"},
    {"text": "Well done is better than well said.", "author": "Benjamin Franklin", "source": "Poor Richard's Almanack, 1737"},
    {"text": "Fall seven times, stand up eight.", "author": "Japanese proverb", "source": None},
]

# Original lines (no attribution needed). {placeholders} are filled from your stats.
TOUGH = {
    "new": ["Zero applications so far. Every offer letter in history started with one application. Send yours.",
            "Researching companies forever is just procrastinating with extra tabs. Apply to one today."],
    "at_risk": ["Your {streak}-day streak dies at midnight. The job market didn't take today off. Neither do you.",
                "0 applications today. Scrolling job boards isn't applying. Send one before you sleep.",
                "{streak} days of work, about to be thrown away over one skipped day. Don't."],
    "broken": ["Your streak is gone. {gap} days with nothing sent. Companies didn't ghost you this week. You ghosted them.",
               "{gap} days since your last application. Nobody is coming to restart this for you. One application. Today."],
    "started": ["{today}/{goal} today. Half-done isn't done. Finish it.",
                "{today} down, {left} to go. The easy part is over. Keep going."],
    "goal_met": ["Goal hit. Don't celebrate too long. Tomorrow resets to zero.",
                 "{today} today. Good. Now do it again tomorrow. That's the whole secret."],
}
KIND = {
    "new": ["Day one starts with one application. You don't need to feel ready; you just need to send it.",
            "Every person you admire sent applications that got ignored. Start your streak today."],
    "at_risk": ["You've shown up {streak} days in a row. You can do one more. You always have.",
                "One application keeps your {streak}-day streak alive. You've done this {total} times before."],
    "broken": ["Streaks break. People who get hired restart them. You've sent {total} applications before; you can send one now.",
               "Your best streak was {best} days. You've done it once, so you can do it again. Start today."],
    "started": ["{today}/{goal} today. You're on the board. {left} more and the day is won.",
                "Nice start. {left} more to hit your goal. You've got this."],
    "goal_met": ["Goal hit: {today} today. That's how offers happen: boring, daily, relentless. Proud of you.",
                 "Done for today. {streak}-day streak. Your future self is going to thank you for this."],
}


def _pick(options: list[str], seed: str) -> str:
    return options[int(hashlib.md5(seed.encode()).hexdigest(), 16) % len(options)]


def compute(times: list[str], tz_offset_min: int = 0, goal: int = 1, style: str = "both") -> dict:
    """tz_offset_min = JavaScript's getTimezoneOffset() (minutes to ADD to local time to get UTC)."""
    goal = max(1, min(int(goal or 1), 50))
    shift = timedelta(minutes=-int(tz_offset_min or 0))
    days = Counter((datetime.fromisoformat(t).astimezone(timezone.utc) + shift).date() for t in times)
    today = (datetime.now(timezone.utc) + shift).date()
    yesterday = today - timedelta(days=1)

    # current streak: counts back from today (or from yesterday if today is still empty: "at risk")
    streak, d = 0, today if days[today] else yesterday
    while days[d]:
        streak += 1
        d -= timedelta(days=1)

    best, run, prev = 0, 0, None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best, prev = max(best, run), d

    total = sum(days.values())
    last = max(days) if days else None
    gap = (today - last).days if last else None
    t = days[today]
    if total == 0:
        state = "new"
    elif t >= goal:
        state = "goal_met"
    elif t > 0:
        state = "started"
    elif streak > 0:
        state = "at_risk"
    else:
        state = "broken"

    vals = dict(streak=streak, best=best, total=total, gap=gap or 0, today=t, goal=goal, left=max(0, goal - t))
    seed = f"{today}-{state}"
    if style == "tough":
        pool = TOUGH[state]
    elif style == "kind":
        pool = KIND[state]
    else:  # both: tough when slipping, kind when you're showing up
        pool = TOUGH[state] if state in {"at_risk", "broken", "new"} else KIND[state]
    message = _pick(pool, seed).format(**vals)
    # A second line from the other voice, so "both" really gives both.
    second = None
    if style == "both" and state in {"at_risk", "broken"}:
        second = _pick(KIND[state], seed + "k").format(**vals)

    return {
        **vals,
        "state": state,
        "message": message,
        "second": second,
        "quote": QUOTES[int(hashlib.md5(str(today).encode()).hexdigest(), 16) % len(QUOTES)],
        "last7": [{"date": str(today - timedelta(days=i)), "count": days[today - timedelta(days=i)]} for i in range(6, -1, -1)],
    }
