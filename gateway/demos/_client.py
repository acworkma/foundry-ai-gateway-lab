"""Shared helpers for the AI gateway demo clients.

Every demo points the OpenAI SDK at the APIM gateway (``GATEWAY_BASE_URL``) and
authenticates with an APIM subscription key (``GATEWAY_SUBSCRIPTION_KEY``). APIM
then forwards the request to the Foundry inference endpoint using its managed
identity, so the demos never see a Foundry key.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# Keep emoji/smart-quotes legible on Windows terminals.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# The storyteller models available behind the gateway.
MODELS = ["gpt-5.2", "DeepSeek-V3.2", "Mistral-Large-3"]

STORYTELLER_SYSTEM = (
    "You are the Storyteller: a warm, vivid narrator. Tell compact, "
    "imaginative stories with a clear beginning, middle, and end."
)


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(
            f"Missing {name}. Set it in .env (run gateway/infra deploy first, "
            "then populate GATEWAY_BASE_URL and GATEWAY_SUBSCRIPTION_KEY)."
        )
    return value


def gateway_client() -> OpenAI:
    """OpenAI client whose base_url is the APIM gateway, keyed by a sub key."""
    base_url = _require("GATEWAY_BASE_URL")
    sub_key = _require("GATEWAY_SUBSCRIPTION_KEY")
    return OpenAI(
        base_url=base_url,
        api_key="unused",  # APIM uses the subscription key header, not bearer.
        default_headers={"Ocp-Apim-Subscription-Key": sub_key},
    )


def tell_story(client: OpenAI, model: str, prompt: str, **extra) -> object:
    """Send one storyteller chat-completion through the gateway."""
    return client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": STORYTELLER_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        **extra,
    )
