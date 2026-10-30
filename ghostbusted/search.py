# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Tavily: the evidence engine. All investigations run in parallel."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from tavily import AsyncTavilyClient

from . import config

log = logging.getLogger("ghostbusted.search")
_client: AsyncTavilyClient | None = None


def client() -> AsyncTavilyClient:
    global _client
    if _client is None:
        _client = AsyncTavilyClient(api_key=config.TAVILY_API_KEY)
    return _client


async def extract_page(url: str) -> str:
    try:
        res = await client().extract(urls=[url], extract_depth="advanced", format="markdown")
        results = res.get("results") or []
        return (results[0].get("raw_content") or "")[:15000] if results else ""
    except Exception as e:
        log.warning("extract failed for %s: %s", url, e)
        return ""


def investigations(company: str, title: str) -> dict[str, dict[str, Any]]:
    """Each investigation = one Tavily query aimed at one ghost-job signal."""
    return {
        "layoffs": dict(label="Layoffs & hiring freezes",
                        query=f"{company} layoffs OR hiring freeze",
                        topic="news", time_range="year", max_results=5),
        "reposts": dict(label="Repost history",
                        query=f'"{company}" "{title}" job posting',
                        max_results=6),
        "applicant_reports": dict(label="Applicant reports",
                                  query=f"{company} ghosted applicants no response interview experience",
                                  include_domains=["reddit.com", "teamblind.com", "glassdoor.com", "fishbowlapp.com"],
                                  max_results=6),
        "careers_page": dict(label="Official careers page",
                             query=f"{company} careers {title}",
                             max_results=5),
        "company_health": dict(label="Company health",
                               query=f"{company} funding revenue growth hiring 2026",
                               topic="news", time_range="year", max_results=5),
    }


async def _run(key: str, spec: dict[str, Any]) -> tuple[str, dict]:
    params = {k: v for k, v in spec.items() if k != "label"}
    try:
        res = await client().search(search_depth="advanced", include_answer="basic", **params)
        hits = [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": (r.get("content") or "")[:600],
             "date": r.get("published_date")}
            for r in res.get("results", [])
        ]
        return key, {"label": spec["label"], "answer": res.get("answer"), "results": hits}
    except Exception as e:
        log.warning("search %s failed: %s", key, e)
        return key, {"label": spec["label"], "answer": None, "results": [], "error": str(e)}


async def investigate(company: str, title: str, on_done=None) -> dict[str, dict]:
    specs = investigations(company, title)
    out: dict[str, dict] = {}
    tasks = [asyncio.create_task(_run(k, s)) for k, s in specs.items()]
    for fut in asyncio.as_completed(tasks):
        key, data = await fut
        out[key] = data
        if on_done:
            await on_done(key, data)
    return out
