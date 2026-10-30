# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""Central configuration. Everything is overridable with environment variables."""
import os
from pathlib import Path

try:  # optional .env support
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# Model routing: small model for fast/cheap calls, big model for the verdict.
# Run `python -m ghostbusted.models` to list the exact IDs available on your account.
MODEL_NANO = os.getenv("MODEL_NANO", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")
MODEL_SUPER = os.getenv("MODEL_SUPER", "nvidia/nemotron-3-super-120b-a12b")
MODEL_ULTRA = os.getenv("MODEL_ULTRA", "nvidia/Nemotron-3-Ultra-550b-a55b")

DB_PATH = Path(os.getenv("GB_DB_PATH", Path(__file__).resolve().parent.parent / "data" / "ghostbusted.db"))

# Demo mode: runs the full app with canned API responses (no keys needed).
DEMO_MODE = os.getenv("GB_DEMO", "").lower() in {"1", "true", "yes"} or not (NEBIUS_API_KEY and TAVILY_API_KEY)

FOLLOWUP_DAYS = int(os.getenv("GB_FOLLOWUP_DAYS", "7"))

# Public demo protection (set these on your public deploy; 0 = no limit, for local use).
PUBLIC = os.getenv("GB_PUBLIC", "").lower() in {"1", "true", "yes"}
LIMIT_PER_VISITOR = int(os.getenv("GB_LIMIT_PER_VISITOR", "5" if PUBLIC else "0"))   # paid actions per visitor per day
LIMIT_TOTAL = int(os.getenv("GB_LIMIT_TOTAL", "150" if PUBLIC else "0"))            # paid actions for everyone per day
