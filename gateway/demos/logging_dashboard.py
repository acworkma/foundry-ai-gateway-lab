"""Demo: LLM logging (prompts + completions) -> Azure Monitor.

The main /storyteller API has the `largeLanguageModel` diagnostic enabled, and an
Azure Monitor diagnostic setting routes the AI-gateway `GatewayLlmLogs` category
to the Log Analytics workspace. Every governed call is logged there in the
`ApiManagementGatewayLlmLog` table — token usage plus the full prompt and
completion — for auditing, billing, and model evaluation.

This demo sends a couple of uniquely tagged storyteller prompts through the
gateway, then queries Log Analytics and prints the reconstructed
prompt -> completion pairs for that tag.

Auth is keyless: DefaultAzureCredential (your `az login` / managed identity).

Run:
    uv run python gateway/demos/logging_dashboard.py
"""

from __future__ import annotations

import os
import time

import httpx
from _client import STORYTELLER_SYSTEM
from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from dotenv import load_dotenv

load_dotenv()

BASE = os.environ["GATEWAY_BASE_URL"]  # main /storyteller API (LLM logging enabled)
KEY = os.environ["GATEWAY_SUBSCRIPTION_KEY"]
WORKSPACE_ID = os.environ["LOG_ANALYTICS_WORKSPACE_ID"]

TAG = f"AUDIT-{int(time.time()) % 100000}"
PROMPTS = [
    f"{TAG} Tell a one-sentence story about a cartographer who maps dreams.",
    f"{TAG} Tell a one-sentence story about a beekeeper who tends comets.",
]

# Join each logged request with its response by CorrelationId, then keep only the
# rows for this run's tag. Mirrors the Microsoft-documented auditing query.
KQL = """
ApiManagementGatewayLlmLog
| where TimeGenerated > ago(1h)
| extend RequestArray = parse_json(RequestMessages)
| extend ResponseArray = parse_json(ResponseMessages)
| mv-expand RequestArray
| mv-expand ResponseArray
| project CorrelationId, DeploymentName,
          RequestContent = tostring(RequestArray.content),
          ResponseContent = tostring(ResponseArray.content)
| summarize
    Input = strcat_array(make_list(RequestContent), " "),
    Output = strcat_array(make_list(ResponseContent), " "),
    Model = any(DeploymentName)
    by CorrelationId
| where Input has "{tag}"
| project Model, Input, Output
"""


def send_traffic() -> None:
    headers = {"Ocp-Apim-Subscription-Key": KEY, "Content-Type": "application/json"}
    with httpx.Client(timeout=60) as client:
        for prompt in PROMPTS:
            body = {
                "model": "gpt-5.2",
                "messages": [
                    {"role": "system", "content": STORYTELLER_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
            }
            r = client.post(f"{BASE}/chat/completions", json=body, headers=headers)
            r.raise_for_status()
    print(f"Sent {len(PROMPTS)} tagged prompts (tag={TAG}).")


def query_logs(minutes: int = 10) -> list:
    client = LogsQueryClient(DefaultAzureCredential())
    query = KQL.replace("{tag}", TAG)
    deadline = time.time() + minutes * 60
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        resp = client.query_workspace(WORKSPACE_ID, query, timespan=None)
        if resp.status == LogsQueryStatus.SUCCESS and resp.tables and resp.tables[0].rows:
            return resp.tables[0].rows
        print(f"  ...no rows yet (attempt {attempt}); LLM logs ingest with a delay, retrying in 30s")
        time.sleep(30)
    return []


def main() -> None:
    print(f"LLM logging demo -> ApiManagementGatewayLlmLog (workspace {WORKSPACE_ID})")
    print("=" * 60)
    send_traffic()
    print("Querying Log Analytics for the logged prompts and completions...")
    rows = query_logs()
    if not rows:
        print("\nNo rows returned yet. Resource-log ingestion to Log Analytics can lag "
              "10-30 min on first enablement; re-run the query later. The KQL used:\n")
        print(KQL.replace("{tag}", TAG))
        return
    for model, inp, out in rows:
        print(f"\n[model] {model}")
        print(f"[prompt]     {inp.strip()[:200]}")
        print(f"[completion] {out.strip()[:200]}")
    print("\nEvery governed call is logged with its prompt and completion — auditable "
          "in Log Analytics for billing, debugging, and model evaluation.")


if __name__ == "__main__":
    main()
