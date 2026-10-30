# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Resume keyword gap analysis. Pure Python: no model or search calls, so it costs nothing.

Nemotron Nano extracts required/preferred skills from the posting (in the parse step that already runs);
this module checks which of them appear in your resume.
"""
from __future__ import annotations

import re
from collections import Counter

# Common alternate spellings, so "Postgres" on a resume matches "PostgreSQL" in a posting.
ALIASES: dict[str, list[str]] = {
    "javascript": ["js", "ecmascript"],
    "typescript": ["ts"],
    "postgresql": ["postgres", "psql"],
    "kubernetes": ["k8s"],
    "machine learning": ["ml"],
    "artificial intelligence": ["ai"],
    "natural language processing": ["nlp"],
    "large language models": ["llm", "llms"],
    "amazon web services": ["aws"],
    "aws": ["amazon web services"],
    "google cloud platform": ["gcp", "google cloud"],
    "gcp": ["google cloud platform", "google cloud"],
    "microsoft azure": ["azure"],
    "node.js": ["node", "nodejs"],
    "react": ["react.js", "reactjs"],
    "next.js": ["nextjs"],
    "vue": ["vue.js", "vuejs"],
    "a/b testing": ["ab testing", "a/b tests", "split testing", "experimentation"],
    "ci/cd": ["continuous integration", "github actions", "jenkins"],
    "rest apis": ["rest", "restful", "rest api"],
    "microsoft excel": ["excel"],
    "excel": ["microsoft excel", "spreadsheets"],
    "power bi": ["powerbi"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "c#": ["csharp", "c sharp"],
    "golang": ["go"],
    "go": ["golang"],
    "object-oriented programming": ["oop", "object oriented"],
    "data structures": ["data structures and algorithms", "dsa"],
    "user experience": ["ux"],
    "user interface": ["ui"],
}

STOP = {"and", "or", "the", "of", "with", "in", "for", "to", "a", "an", "experience", "knowledge", "skills",
        "strong", "proficiency", "familiarity", "understanding", "ability", "years", "year"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def _present(term: str, text: str) -> bool:
    """Whole-word match that also works for terms like C++, C#, .NET, Node.js, CI/CD."""
    term = _norm(term)
    if not term:
        return False
    pattern = r"(?<![a-z0-9+#])" + re.escape(term) + r"(?![a-z0-9+#])"
    return re.search(pattern, text) is not None


def has_skill(skill: str, resume_text: str) -> bool:
    s = _norm(skill)
    # Short names like "Go", "R", "C" are also everyday words/letters: match them case-sensitively.
    if len(s) <= 2:
        raw = skill.strip()
        cands = [raw] + [a for a in ALIASES.get(s, []) if len(a) > 2]
        return any(re.search(r"(?<![A-Za-z0-9+#])" + re.escape(c) + r"(?![A-Za-z0-9+#])", resume_text or "",
                             0 if c is raw else re.I) for c in cands)
    text = _norm(resume_text)
    if _present(s, text):
        return True
    if any(_present(a, text) for a in ALIASES.get(s, [])):
        return True
    # Multi-word skill: count it if every meaningful word appears ("stakeholder management" ~ "managed stakeholders")
    words = [w for w in re.findall(r"[a-z0-9+#.]+", s) if w not in STOP and len(w) > 2]
    if len(words) >= 2 and all(re.search(r"\b" + re.escape(w[:5]), text) for w in words):
        return True
    return False


def _clean_list(items) -> list[str]:
    seen, out = set(), []
    for it in items or []:
        if not isinstance(it, str):
            continue
        name = it.strip().strip(".")
        key = _norm(name)
        if name and key not in seen and len(name) <= 60:
            seen.add(key)
            out.append(name)
    return out


def match(job: dict, resume: str) -> dict | None:
    """Compare a parsed job's skills with the resume. None if there's no resume or no skills."""
    if not (resume or "").strip():
        return None
    required = _clean_list(job.get("required_skills"))
    preferred = [p for p in _clean_list(job.get("preferred_skills")) if _norm(p) not in {_norm(r) for r in required}]
    if not required and not preferred:
        required = _clean_list(job.get("requirements"))  # fallback for older checks
    if not required and not preferred:
        return None
    matched = [s for s in required + preferred if has_skill(s, resume)]
    missing_required = [s for s in required if s not in matched]
    missing_preferred = [s for s in preferred if s not in matched]
    # Required skills count double toward the keyword score.
    total = 2 * len(required) + len(preferred)
    got = 2 * (len(required) - len(missing_required)) + (len(preferred) - len(missing_preferred))
    return {
        "score": round(100 * got / total) if total else None,
        "matched": matched,
        "missing_required": missing_required,
        "missing_preferred": missing_preferred,
        "required_total": len(required),
        "preferred_total": len(preferred),
    }


def gaps_across_jobs(reports: list[dict], resume: str) -> dict:
    """Which skills are you missing most often across every job you've checked?"""
    missing, have, jobs = Counter(), Counter(), 0
    required_in: Counter = Counter()
    display: dict[str, str] = {}
    for rep in reports:
        m = match((rep or {}).get("job") or {}, resume)
        if not m:
            continue
        jobs += 1
        for s in m["missing_required"]:
            missing[_norm(s)] += 1
            required_in[_norm(s)] += 1
            display.setdefault(_norm(s), s)
        for s in m["missing_preferred"]:
            missing[_norm(s)] += 1
            display.setdefault(_norm(s), s)
        for s in m["matched"]:
            have[_norm(s)] += 1
            display.setdefault(_norm(s), s)
    return {
        "jobs_compared": jobs,
        "top_missing": [{"skill": display[k], "jobs": missing[k], "required_in": required_in[k]}
                        for k in sorted(missing, key=lambda k: (-missing[k], -required_in[k]))[:15]],
        "top_matched": [{"skill": display[k], "jobs": n} for k, n in have.most_common(10)],
    }
