"""Direct-access RBAC demo: prove which models the current identity may call.

Acquires one Entra token for the chosen persona, prints the app roles it
carries, then calls all three per-model APIs through the gateway and reports the
outcome:

  * 200  -> ALLOWED (the token carries the required app role); the model's
            actual reply is printed so you can see a real completion, not just
            a status code.
  * 403  -> DENIED  (validate-azure-ad-token rejected the missing role)

Flip the persona from the command line to watch the access boundary move:

    uv run python direct-access/demos/access_matrix.py coding    # Model.Coding.Invoke
    uv run python direct-access/demos/access_matrix.py general    # Model.General.Invoke
    uv run python direct-access/demos/access_matrix.py user       # signed-in user (az login)

With no argument it falls back to DIRECT_CLIENT_ID/SECRET (or az login). This is
the terminal-friendly centrepiece of the lab.
"""

from __future__ import annotations

import json
import sys
import textwrap

from _client import (
    MODEL_APIS,
    PERSONAS,
    PROMPT,
    call_model,
    get_credential,
    get_token,
    reply_text,
    token_roles,
)

SNIPPET_WIDTH = 200


def _model_of(resp) -> str:
    try:
        data = resp.json()
    except Exception:
        return ""
    if isinstance(data, dict):
        return data.get("model") or data.get("response", {}).get("model", "")
    return ""


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return textwrap.shorten(text, width=SNIPPET_WIDTH, placeholder=" ...")


def main() -> None:
    persona = sys.argv[1].lower() if len(sys.argv) > 1 else None
    if persona is not None and persona not in PERSONAS:
        sys.exit(
            f"Unknown persona '{persona}'. Choose one of: "
            f"{', '.join(PERSONAS)} (or omit for the default credential)."
        )

    label = PERSONAS[persona]["label"] if persona else "default (DIRECT_CLIENT_* / az login)"

    credential = get_credential(persona)
    token = get_token(credential)
    roles = token_roles(token)

    print("=" * 68)
    print("Direct-access model RBAC — access matrix")
    print("=" * 68)
    print(f"Persona:         {label}")
    print(f"Token app roles: {', '.join(roles) if roles else '(none)'}")
    print(f"Prompt:          {PROMPT}")
    print("-" * 68)

    for api in MODEL_APIS:
        resp = call_model(api, token)
        if resp.status_code == 200:
            print(f"  {api['label']:<26}  requires {api['role']:<20}  ->  ALLOWED")
            print(f"      model: {_model_of(resp)}")
            reply = _snippet(reply_text(resp))
            print(f"      reply: {reply or '(no text returned)'}")
        elif resp.status_code == 403:
            verdict = "DENIED   (403 — missing required app role)"
            print(f"  {api['label']:<26}  requires {api['role']:<20}  ->  {verdict}")
        else:
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
