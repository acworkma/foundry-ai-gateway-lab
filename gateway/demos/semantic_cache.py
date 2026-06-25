"""Demo: llm-semantic-cache (vector-similarity response caching).

Sends an initial storyteller prompt (cache miss → backend), then a *semantically
similar but differently worded* prompt. The gateway embeds both prompts, finds
them close in vector space, and returns the cached completion — no backend call,
near-zero latency, identical text. A clearly different prompt misses and hits the
backend again.

Cache hits are detected by latency (cache ≈ instant vs backend ≈ seconds) and by
the response being byte-identical to the first.

Run:
    uv run python gateway/demos/semantic_cache.py
"""

from __future__ import annotations

import os
import random
import time

import httpx
from _client import STORYTELLER_SYSTEM
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["GATEWAY_BASE_URL"].replace("/storyteller", "/storyteller-cache")
KEY = os.environ["GATEWAY_SUBSCRIPTION_KEY"]

# Randomize the subject every run so the "miss" prompts are always novel (cold),
# making the miss -> hit -> miss pattern reproducible even within the cache TTL.
CREATURE = random.choice(["dragon", "griffin", "kraken", "phoenix", "yeti"])
FEAR = random.choice(["fire", "heights", "the dark", "deep water", "thunder"])
OTHER = random.choice(
    ["a submarine captain who finds a city", "a clockmaker who stops time",
     "a gardener who grows stars", "a lighthouse keeper who talks to whales"]
)

PROBES = [
    ("first ask (expect MISS)", f"Tell a short story about a {CREATURE} who is afraid of {FEAR}."),
    ("reworded (expect HIT)", f"Share a brief tale of a {CREATURE} that fears {FEAR}."),
    ("different (expect MISS)", f"Tell a short story about {OTHER}."),
]


def ask(client: httpx.Client, prompt: str) -> tuple[float, str]:
    body = {
        "model": "gpt-5.2",
        "messages": [
            {"role": "system", "content": STORYTELLER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    headers = {"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/json"}
    t0 = time.perf_counter()
    r = client.post(f"{BASE}/chat/completions", json=body, headers=headers)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    return dt, r.json()["choices"][0]["message"]["content"]


def main() -> None:
    print(f"Semantic cache at {BASE}/chat/completions\n" + "=" * 60)
    first_text = None
    with httpx.Client(timeout=60) as client:
        for label, prompt in PROBES:
            dt, text = ask(client, prompt)
            if first_text is None:
                first_text = text
                verdict = "MISS (backend)"
            elif text == first_text:
                verdict = "HIT  (served from cache, identical to first)"
            else:
                verdict = "MISS (backend, different story)"
            print(f"[{label:<24}] {dt:5.2f}s  {verdict}")
    print("\nThe reworded prompt returns the first story verbatim from the semantic "
          "cache; the unrelated prompt produces a fresh story from the backend.")


if __name__ == "__main__":
    main()
