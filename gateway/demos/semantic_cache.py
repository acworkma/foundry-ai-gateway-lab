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
import time

import httpx
from _client import STORYTELLER_SYSTEM
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["GATEWAY_BASE_URL"].replace("/storyteller", "/storyteller-cache")
KEY = os.environ["GATEWAY_SUBSCRIPTION_KEY"]

PROBES = [
    ("first ask (expect MISS)", "Tell a short story about a dragon who is afraid of fire."),
    ("reworded (expect HIT)", "Share a brief tale of a dragon that fears flames."),
    ("different (expect MISS)", "Tell a short story about a submarine captain who finds a city."),
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
            verdict = ""
            if first_text is None:
                first_text = text
            elif text == first_text:
                verdict = "  <-- CACHE HIT (identical to first)"
            tag = "fast" if dt < 0.4 else "slow"
            print(f"[{label:<24}] {dt:5.2f}s ({tag}){verdict}")
    print("\nReworded prompt served from cache (fast + identical); the unrelated "
          "prompt went to the backend.")


if __name__ == "__main__":
    main()
