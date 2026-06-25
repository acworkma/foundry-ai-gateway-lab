"""Demo: llm-token-limit (token rate limiting & quotas).

Repeatedly asks the storyteller for a story through the *throttled* gateway API
(1000 tokens/minute per subscription). APIM returns the remaining/consumed token
budget in response headers each call, and a 429 once the per-minute budget is
spent. This is the gateway protecting a shared backend from runaway consumption.

Run:
    uv run python gateway/demos/token_limit.py
"""

from __future__ import annotations

import os

import httpx
from _client import STORYTELLER_SYSTEM, gateway_client  # noqa: F401  (reuse env load)
from dotenv import load_dotenv

load_dotenv()

# The throttled API lives at /storyteller-throttled (vs /storyteller).
BASE = os.environ["GATEWAY_BASE_URL"].replace("/storyteller", "/storyteller-throttled")
KEY = os.environ["GATEWAY_SUBSCRIPTION_KEY"]
PROMPT = "Tell a vivid three-paragraph story about a clockmaker who repairs time itself."


def main() -> None:
    print(f"Hammering {BASE}/chat/completions (limit: 1000 tokens/min)\n" + "=" * 60)
    body = {
        "model": "gpt-5.2",
        "messages": [
            {"role": "system", "content": STORYTELLER_SYSTEM},
            {"role": "user", "content": PROMPT},
        ],
    }
    headers = {"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/json"}
    with httpx.Client(timeout=60) as client:
        for i in range(1, 11):
            r = client.post(f"{BASE}/chat/completions", json=body, headers=headers)
            remaining = r.headers.get("x-remaining-tokens", "?")
            consumed = r.headers.get("x-tokens-consumed", "?")
            if r.status_code == 429:
                retry = r.headers.get("x-retry-after", r.headers.get("retry-after", "?"))
                print(f"call {i:>2}: 429 THROTTLED — retry after {retry}s "
                      f"(remaining={remaining})")
                print("\nGateway enforced the token budget. ✔")
                return
            used = r.json().get("usage", {}).get("total_tokens", "?")
            print(f"call {i:>2}: 200 OK  used={used:<5} "
                  f"consumed-header={consumed:<6} remaining={remaining}")
    print("\nBudget not exhausted in 10 calls — lower tokens-per-minute to force a 429.")


if __name__ == "__main__":
    main()
