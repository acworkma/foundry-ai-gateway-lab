"""Storyteller fan-out through the AI gateway.

Sends the same storyteller prompt to all three models *through APIM* so every
token is governed by the gateway. This is the centerpiece workload the rest of
the capability demos build on.

Run:
    uv run python gateway/demos/storyteller_via_gateway.py
"""

from __future__ import annotations

from _client import MODELS, gateway_client, tell_story

PROMPT = "Tell a short story about a lighthouse keeper who befriends a storm."


def main() -> None:
    client = gateway_client()
    print(f"Storyteller via gateway -> {len(MODELS)} models\n" + "=" * 60)
    for model in MODELS:
        print(f"\n### {model}")
        try:
            resp = tell_story(client, model, PROMPT)
        except Exception as exc:  # noqa: BLE001 - surface gateway errors verbatim
            print(f"  ERROR: {exc}")
            continue
        print(resp.choices[0].message.content.strip())
        usage = resp.usage
        if usage:
            print(
                f"  [tokens] prompt={usage.prompt_tokens} "
                f"completion={usage.completion_tokens} total={usage.total_tokens}"
            )


if __name__ == "__main__":
    main()
