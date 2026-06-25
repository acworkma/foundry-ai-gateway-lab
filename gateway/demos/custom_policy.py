"""Demo: custom policy (model allow-list + governance headers).

The /storyteller-custom API layers a plain C# policy expression on top of the
shared backend — capability the built-in llm-* policies don't cover:

  * An *allowed* model returns 200 and the response carries governance headers
    (x-gateway-model, x-gateway-served-by, x-gateway-request-id).
  * A *disallowed* model is rejected at the gateway with 400 model_not_allowed,
    never reaching Foundry.

Run:
    uv run python gateway/demos/custom_policy.py
"""

from __future__ import annotations

import os

import httpx
from _client import STORYTELLER_SYSTEM
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["GATEWAY_BASE_URL"].replace("/storyteller", "/storyteller-custom")
KEY = os.environ["GATEWAY_SUBSCRIPTION_KEY"]

PROMPT = "Tell a two-sentence story about a curious robot."
GOVERNANCE_HEADERS = ("x-gateway-model", "x-gateway-served-by", "x-gateway-request-id")


def call(client: httpx.Client, model: str) -> httpx.Response:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": STORYTELLER_SYSTEM},
            {"role": "user", "content": PROMPT},
        ],
    }
    headers = {"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/json"}
    return client.post(f"{BASE}/chat/completions", json=body, headers=headers)


def main() -> None:
    print(f"Custom policy at {BASE}/chat/completions\n" + "=" * 60)
    with httpx.Client(timeout=60) as client:
        # 1) Allowed model -> 200 + governance headers.
        r = call(client, "gpt-5.2")
        print(f"[allowed  gpt-5.2       ] HTTP {r.status_code}")
        for h in GOVERNANCE_HEADERS:
            print(f"    {h}: {r.headers.get(h, '<missing>')}")

        # 2) Disallowed model -> blocked at the gateway with 400.
        r = call(client, "gpt-4o-mini")
        print(f"\n[blocked  gpt-4o-mini   ] HTTP {r.status_code}")
        try:
            print(f"    body: {r.json()['error']['message']}")
        except Exception:
            print(f"    body: {r.text[:200]}")

    print("\nThe allow-listed model is served and stamped with governance headers; "
          "the unapproved model is rejected by the custom policy before Foundry.")


if __name__ == "__main__":
    main()
