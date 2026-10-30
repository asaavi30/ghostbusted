# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Nemotron on Nebius Token Factory, with task-based model routing.

Routing (what the judges asked for):
  nano  -> fast structured extraction (parse the job posting)
  super -> everyday writing (follow-up emails, fit notes)
  ultra -> the hard reasoning call (the ghost verdict over all the evidence)
If a model ID is unavailable, we fall back down the chain so the app never dies mid-demo.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from openai import AsyncOpenAI

from . import config

log = logging.getLogger("ghostbusted.llm")

ROUTES = {"nano": config.MODEL_NANO, "super": config.MODEL_SUPER, "ultra": config.MODEL_ULTRA}
FALLBACK = {"ultra": ["super", "nano"], "super": ["nano"], "nano": ["super"]}

_client: AsyncOpenAI | None = None

# Simple in-process usage log so the UI can show which model did what.
usage_log: list[dict[str, Any]] = []


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY, timeout=90, max_retries=2)
    return _client


def _strip_reasoning(text: str) -> str:
    # Nemotron reasoning models may emit <think>...</think> before the answer.
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


def _parse_json(text: str) -> dict:
    text = _strip_reasoning(text)
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


async def chat(tier: str, system: str, user: str, *, json_mode: bool = False, max_tokens: int = 1500,
               temperature: float = 0.2) -> tuple[str, str]:
    """Returns (text, model_used)."""
    tiers = [tier] + FALLBACK.get(tier, [])
    last_err: Exception | None = None
    for t in tiers:
        model = ROUTES[t]
        t0 = time.perf_counter()
        try:
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            try:
                resp = await client().chat.completions.create(**kwargs)
            except Exception as e:  # some models reject response_format; retry without it
                if json_mode and "response_format" in str(e):
                    kwargs.pop("response_format")
                    resp = await client().chat.completions.create(**kwargs)
                else:
                    raise
            text = resp.choices[0].message.content or ""
            # Reasoning models can spend the whole budget thinking and get cut off before answering.
            # If the answer was truncated, retry once with a much bigger budget.
            if resp.choices[0].finish_reason == "length" and (json_mode and "}" not in _strip_reasoning(text)):
                log.warning("model %s ran out of tokens; retrying with a larger budget", model)
                kwargs["max_tokens"] = max_tokens * 3
                resp = await client().chat.completions.create(**kwargs)
                text = resp.choices[0].message.content or ""
            usage_log.append({"tier": t, "model": model, "ms": int((time.perf_counter() - t0) * 1000),
                              "tokens": getattr(resp.usage, "total_tokens", None)})
            if not _strip_reasoning(text):
                raise RuntimeError("empty answer")
            return _strip_reasoning(text), model
        except Exception as e:
            log.warning("model %s failed: %s", model, e)
            last_err = e
    raise RuntimeError(f"All models failed: {last_err}")


async def chat_json(tier: str, system: str, user: str, **kw) -> tuple[dict, str]:
    text, model = await chat(tier, system, user, json_mode=True, **kw)
    try:
        return _parse_json(text), model
    except Exception:
        pass
    # Only "repair" text that actually contains an answer; otherwise ask the next model up from scratch.
    if "{" in text and len(text) > 40:
        try:
            fixed, _ = await chat("nano", "Return ONLY valid JSON. No prose.", f"Fix into valid JSON:\n{text}",
                                  max_tokens=3000)
            return _parse_json(fixed), model
        except Exception:
            pass
    nxt = {"nano": "super", "super": "ultra"}.get(tier, "super")
    text, model = await chat(nxt, system, user, json_mode=True, **kw)
    return _parse_json(text), model
