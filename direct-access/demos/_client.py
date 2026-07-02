"""Shared helpers for the direct-access model RBAC demo.

Unlike the storyteller gateway demos (which authenticate with only an APIM
subscription key), the direct-access lab layers **Entra ID authorization** on
top: every call carries a bearer token, and each per-model API requires a
specific app role (Model.Coding.Invoke or Model.General.Invoke). APIM's
validate-azure-ad-token policy rejects tokens without the right role with 403,
so a caller can only reach the models their identity is entitled to.

Credential resolution:
- If DIRECT_CLIENT_ID + DIRECT_CLIENT_SECRET (+ DIRECT_TENANT_ID) are set, a
  ClientSecretCredential is used (service-principal path — fully scriptable).
- Otherwise DefaultAzureCredential is used (interactive user / az login path),
  so group-based access can be demonstrated with a signed-in developer.
"""

from __future__ import annotations

import base64
import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

GATEWAY_BASE_URL = os.environ.get("DIRECT_GATEWAY_BASE_URL", "https://aig-acw.azure-api.net")
RESOURCE_APP_ID = os.environ.get("DIRECT_RESOURCE_APP_ID", "")
TENANT_ID = os.environ.get("DIRECT_TENANT_ID", "")

PROMPT = "Reply in one short sentence: what is an API gateway?"

# Registry of the three per-model APIs exposed by the gateway. `sub_key_env`
# names the .env variable holding the product subscription key for that API.
MODEL_APIS = [
    {
        "label": "gpt-5.3-codex  (Coding)",
        "path": "/codex/responses",
        "schema": "responses",
        "role": "Model.Coding.Invoke",
        "sub_key_env": "DIRECT_CODING_SUB_KEY",
    },
    {
        "label": "gpt-5.2        (General)",
        "path": "/gpt52/chat/completions",
        "schema": "chat",
        "role": "Model.General.Invoke",
        "sub_key_env": "DIRECT_GENERAL_SUB_KEY",
    },
    {
        "label": "Mistral-Large-3 (General)",
        "path": "/mistral/chat/completions",
        "schema": "chat",
        "role": "Model.General.Invoke",
        "sub_key_env": "DIRECT_GENERAL_SUB_KEY",
    },
]


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(
            f"Missing {name}. Set it in .env (deploy direct-access/infra first, "
            "then populate DIRECT_RESOURCE_APP_ID, DIRECT_TENANT_ID, the product "
            "subscription keys, and either DIRECT_CLIENT_ID/SECRET or use az login)."
        )
    return value


def get_credential():
    """ClientSecretCredential if SP env vars are set, else DefaultAzureCredential."""
    client_id = os.environ.get("DIRECT_CLIENT_ID")
    client_secret = os.environ.get("DIRECT_CLIENT_SECRET")
    tenant_id = os.environ.get("DIRECT_TENANT_ID")
    if client_id and client_secret and tenant_id:
        from azure.identity import ClientSecretCredential

        return ClientSecretCredential(tenant_id, client_id, client_secret)
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def get_token(credential) -> str:
    """Acquire a bearer token whose audience is the direct-access resource app."""
    resource_app = _require("DIRECT_RESOURCE_APP_ID")
    scope = f"api://{resource_app}/.default"
    return credential.get_token(scope).token


def token_roles(token: str) -> list[str]:
    """Decode the `roles` claim from a JWT (no signature validation — display only)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return claims.get("roles", []) or []
    except Exception:
        return []


def call_model(api: dict, token: str) -> httpx.Response:
    """Call one model API through the gateway with bearer token + subscription key."""
    sub_key = _require(api["sub_key_env"])
    url = f"{GATEWAY_BASE_URL}{api['path']}"
    if api["schema"] == "responses":
        body = {"input": PROMPT}
    else:
        body = {"messages": [{"role": "user", "content": PROMPT}]}
    headers = {
        "Authorization": f"Bearer {token}",
        "Ocp-Apim-Subscription-Key": sub_key,
        "Content-Type": "application/json",
    }
    return httpx.post(url, headers=headers, json=body, timeout=60)
