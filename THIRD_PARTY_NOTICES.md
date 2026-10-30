# Third-party notices

GhostBusted's own code is © 2026 Asaavi Anil Tupsounder, licensed under Apache 2.0. It contains no code copied from other projects. It **uses** the following open-source libraries and services, which are installed separately (they are not bundled in this repository). All of their licenses are permissive and compatible with Apache 2.0.

## Python libraries (installed from `requirements.txt`)

| Library | Used for | License |
|---|---|---|
| [FastAPI](https://github.com/fastapi/fastapi) | Web server and API | MIT |
| [Starlette](https://github.com/encode/starlette) (via FastAPI) | Web framework | BSD-3-Clause |
| [Uvicorn](https://github.com/encode/uvicorn) | Runs the server | BSD-3-Clause |
| [Pydantic](https://github.com/pydantic/pydantic) | Request validation | MIT |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | OpenAI-compatible client for Nebius Token Factory | Apache-2.0 |
| [HTTPX](https://github.com/encode/httpx) (via the SDK) | HTTP client | BSD-3-Clause |
| [tavily-python](https://github.com/tavily-ai/tavily-python) | Tavily Search and Extract | MIT |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Loads `.env` settings | BSD-3-Clause |
| [python-multipart](https://github.com/Kludex/python-multipart) | Resume file uploads | Apache-2.0 |
| [pypdf](https://github.com/py-pdf/pypdf) | Reads PDF resumes | BSD-3-Clause |
| [python-docx](https://github.com/python-openxml/python-docx) | Reads Word resumes | MIT |

## Fonts (loaded from Google Fonts at runtime)

| Font | License |
|---|---|
| Space Grotesk | SIL Open Font License 1.1 |
| JetBrains Mono | SIL Open Font License 1.1 |

## Services (used through their APIs, under their own terms)

- **NVIDIA Nemotron models** served by **Nebius Token Factory** (model weights are not redistributed here).
- **Tavily** Search and Extract APIs.

## Quotes shown in the streak feature

Short quotes are shown with credit to their authors: Benjamin Franklin, Francis Bacon and Louisa May Alcott (public-domain works), a Japanese proverb, and one short line by Wayne Gretzky. All other motivational lines are original to GhostBusted.

## Demo data

Demo mode uses two fictional companies, "Quillery Analytics" and "Tandemvolt Robotics", with made-up evidence and `example.com` links. Any resemblance to real companies is unintended.
