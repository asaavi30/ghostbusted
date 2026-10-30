# Copyright 2026 Asaavi Anil Tupsounder
# SPDX-License-Identifier: Apache-2.0
"""List the Nemotron model IDs available on your Token Factory account.

Usage:  python -m ghostbusted.models
Then set MODEL_NANO / MODEL_SUPER / MODEL_ULTRA in .env to the exact IDs printed.
"""
from openai import OpenAI

from . import config

if __name__ == "__main__":
    c = OpenAI(base_url=config.NEBIUS_BASE_URL, api_key=config.NEBIUS_API_KEY)
    ids = sorted(m.id for m in c.models.list().data)
    nem = [i for i in ids if "nemotron" in i.lower()]
    print("Nemotron models on your account:")
    for i in nem or ["(none found; showing all)"] + ids:
        print("  ", i)
