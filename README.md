# 👻 GhostBusted: is this job even real?

**Your personal AI job-hunt agent: it busts ghost jobs with receipts, keeps watching every application, and keeps you consistent with daily streaks.**

Built for the **Nebius x NVIDIA Global AI Hackathon, Personal AI Track.**
© 2026 Asaavi Anil Tupsounder · License: Apache 2.0.

**Live demo:** [https://ghostbusted-xxxx.onrender.com](https://ghostbusted.onrender.com)

---

## The problem
Ghost jobs are postings with no real intent to hire: evergreen "talent pools," roles reposted for months, listings left up during hiring freezes. Gen Z job seekers send hundreds of applications into them and hear nothing back. There is no way to tell from the posting alone.

## What GhostBusted does
1. **Paste a job link or description.**
2. Your agent **investigates live**, in parallel:
   - layoffs and hiring freezes at the company
   - whether the same role has been reposted again and again
   - applicant reports of ghosting on Reddit, Blind and Glassdoor
   - whether the role appears on the company's own careers page
   - the company's recent funding and health
   - red flags in the posting text (talent-pool language, no salary, stale date, unrealistic entry-level requirements)
3. You get a **Ghost Meter (0–100)**, a one-line verdict, **receipts linked to sources**, your **fit score** against your resume, and what to do next.
4. **It keeps working after that (Personal AI):** it remembers your resume, goals and every job you've checked. A daily job re-investigates your active applications, **alerts you if a job turns into a ghost** when one is due, and auto-marks jobs as ghosted after 30 days of silence.

5. **Company ghost history:** every company you've checked, ranked by its average ghost score ("Ghost factory," "Mixed signals," "Hires for real"), with each job's score and whether that company ghosted you. When you check a new job, it reminds you of your history with that company. It's computed from your own data, so it makes no extra model or search calls.
6. **Resume keyword gaps:** for every job, the skills the posting asks for, split into missing-required, missing-nice-to-have and already in your resume, with a keyword match score. The Profile tab ranks the skills you're missing most often across every job you've checked. Nemotron Nano extracts the skills during its existing parse step, and the matching (with aliases like Postgres = PostgreSQL) runs in plain Python at no extra cost.
7. **Worth applying: tailor your resume.** The Profile tab lists every job the agent recommends (low ghost score, not "Skip it"), least ghosty first, each with its keyword match and the required and nice-to-have skills your resume is missing.
8. **Best bets: where your next hour of applying should go.** Every job you've saved but not applied to, ranked by a 0–100 reply-odds score that multiplies four factors: is it real (1 − ghost score), is it fresh (posting age), do you fit (keyword match), and does this company actually reply to you (Response Radar). Each job shows its factor bars, a plain-English reason, and the missing skills dragging it down. Your top N (your daily goal) are marked "Apply today." Once you have 5 outcomes, a calibration box checks whether high-odds jobs really replied more often, so the advice is graded against your real results. Other tools rank jobs by resume match only. Pure Python, no API calls.
9. **Response Radar: ghost scores that learn from real outcomes.** Other tools only guess from the posting. GhostBusted records what actually happened after you applied (replied, interviewed, rejected, ghosted) and shows each company's real reply rate and reply time. It then adjusts future ghost scores for that company: +12 per ghosting, −10 per reply, capped, and always shown on screen. The data is yours and grows with every application, which is hard for anyone to copy. Next step: opt-in, anonymous pooling across users.
10. **Application streaks:** a daily goal, a 🔥 streak with 7-day history, "+1 applied elsewhere" for jobs you didn't check here, and motivation in your chosen style (tough love, encouraging, or both). Quotes are limited to ones with documented sources, always credited.
11. **Resume upload:** PDF, Word (.docx) or text, read locally with no AI call. The original file is kept for future ATS checks.
12. **Light and dark mode** that follows your system setting and remembers your choice.

## How it uses NVIDIA Nemotron + Nebius Token Factory
All model calls go to **NVIDIA Nemotron on Nebius Token Factory** (OpenAI-compatible API), **routed by task** so the app stays fast and credits stretch further:

| Task | Model | Why |
|---|---|---|
| Parse the posting into structured JSON | **Nemotron 3 Nano** | Fast, cheap extraction |
| Final ghost verdict over all evidence + resume fit | **Nemotron 3 Ultra** | The hard multi-source reasoning call |

If a model is unavailable, `llm.py` falls back down the chain so a demo never dies. Nemotron's `<think>` traces are stripped, JSON is validated and repaired, and **any source URL the model cites that wasn't in the Tavily evidence is dropped**, so the receipts can't be hallucinated.

## How it uses Tavily
Tavily is the evidence engine:
- **Tavily Extract** reads the job posting from its URL.
- **Five Tavily Search investigations run concurrently** (`asyncio`), each aimed at one ghost-job signal and using `topic="news"`, `time_range`, and `include_domains` (Reddit/Blind/Glassdoor) where they help.
- Results stream into the UI as each investigation finishes, so you watch the agent work.

## Nebius services
- **Nebius Token Factory:** all inference (Nemotron Nano / Ultra).
- **Nebius Serverless Endpoint:** hosts the web app (`Dockerfile`, port 8000).
- **Nebius Serverless Job:** runs the daily watcher (`python -m ghostbusted.daily`) on a schedule.

## Architecture
```
Browser ──SSE──> FastAPI (main.py)
                   ├─ analyzer.py   pipeline: read → parse → investigate → red flags → verdict
                   │    ├─ search.py  Tavily Extract + 5 parallel Tavily Searches
                   │    └─ llm.py     Nemotron routing on Token Factory (nano/ultra + fallback)
                   ├─ db.py         SQLite memory: profile, jobs, score history, alerts
                   └─ daily.py      always-on watcher (Nebius Serverless Job)
```

## Run it locally
```bash
git clone <this repo> && cd ghostbusted
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add NEBIUS_API_KEY and TAVILY_API_KEY
python -m ghostbusted.models  # prints the Nemotron model IDs on your account; paste them into .env
uvicorn ghostbusted.main:app --reload
```
Open http://localhost:8000.

**No keys?** The app starts in **demo mode** with realistic canned data for two fictional companies, so you can click through the whole experience. Real runs start automatically once both keys are set.

Run the daily watcher by hand:
```bash
python -m ghostbusted.daily
```

## Deploy on Nebius
1. Build and push the image: `docker build -t <registry>/ghostbusted:latest . && docker push <registry>/ghostbusted:latest`
2. **Serverless Endpoint:** create an endpoint from the image, expose port `8000`, and set `NEBIUS_API_KEY`, `TAVILY_API_KEY` and the `MODEL_*` variables. Mount a volume and set `GB_DB_PATH` to keep memory across restarts.
3. **Serverless Job:** create a scheduled job (daily) from the same image with the command `python -m ghostbusted.daily` and the same env vars and volume.

## API
| Method | Path | |
|---|---|---|
| POST | `/api/analyze` | `{url}` or `{text}` → Server-Sent Events: live steps, then the report |
| GET | `/api/applications` | your tracked jobs |
| PATCH | `/api/applications/{id}` | `{status}`: saved, applied, interviewing, offer, rejected, ghosted |
| GET/PUT | `/api/profile` | resume and goals (memory) |
| GET | `/api/events` | ghost alerts |
| POST | `/api/daily` | run the daily watcher now |

## Responsible design
- The verdict is evidence-based and shows its sources. When evidence is thin, the model is told to stay near the middle of the scale and report low confidence.
- Your resume and job history stay in your own database file. Nothing is sent anywhere except the model and search calls needed for an analysis.
- Demo data uses fictional companies.

## Built during the submission period
Everything in this repo was built during the hackathon submission period.

## Feedback on Nebius Token Factory and NVIDIA tools
_Fill in before submitting: what worked well (OpenAI compatibility, latency, model routing), what was confusing, and what you'd improve._

## License
© 2026 Asaavi Anil Tupsounder. Licensed under the [Apache License 2.0](LICENSE).

- You may use, modify and share this code, but every copy must keep the `LICENSE` and `NOTICE` files and the copyright notices crediting Asaavi Anil Tupsounder, and must mark which files were changed.
- The license does **not** grant rights to use the name "GhostBusted" or its branding.
- Third-party libraries and their licenses are listed in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). All are permissive and compatible with Apache 2.0.
- GhostBusted is not affiliated with the "Ghostbusters" franchise, NVIDIA, Nebius or Tavily.
