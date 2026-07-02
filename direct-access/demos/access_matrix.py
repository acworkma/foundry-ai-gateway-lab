"""Direct-access RBAC demo: prove which models the current identity may call.

Acquires one Entra token for the configured identity (service principal via
DIRECT_CLIENT_ID/SECRET, or the signed-in user via az login), prints the app
roles it carries, then calls all three per-model APIs through the gateway and
reports the outcome:

  * 200  -> allowed (the token carries the required app role)
  * 403  -> denied  (validate-azure-ad-token rejected the missing role)

Run it as the Coding client and as the General client to see the access
boundary flip. This is the terminal-friendly centrepiece of the lab.
"""

from __future__ import annotations

import json

from _client import MODEL_APIS, call_model, get_credential, get_token, token_roles


def _model_of(resp) -> str:
    try:
        data = resp.json()
    except Exception:
        return ""
    if isinstance(data, dict):
        return data.get("model") or data.get("response", {}).get("model", "")
    return ""


def main() -> None:
    credential = get_credential()
    token = get_token(credential)
    roles = token_roles(token)

    print("=" * 68)
    print("Direct-access model RBAC — access matrix")
    print("=" * 68)
    print(f"Token app roles: {', '.join(roles) if roles else '(none)'}")
    print("-" * 68)

    for api in MODEL_APIS:
        resp = call_model(api, token)
        if resp.status_code == 200:
            verdict = f"ALLOWED  (returned model: {_model_of(resp)})"
        elif resp.status_code == 403:
            verdict = "DENIED   (403 — missing required app role)"
        else:
            detail = ""
            try:
                detail = json.dumps(resp.json().get("error", resp.json()))[:120]
            except Exception:
                detail = resp.text[:120]
            verdict = f"HTTP {resp.status_code}  {detail}"
        print(f"  {api['label']:<26}  requires {api['role']:<20}  ->  {verdict}")

    print("-" * 68)
    print("Tip: the model field is forced server-side, so a codex-scoped caller")
    print("cannot reach gpt-5.2/Mistral by editing the request body.")


if __name__ == "__main__":
    main()
