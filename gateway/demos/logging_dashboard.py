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

# LLM logs can land in one of two tables depending on the diagnostic setting's
# destination type:
#   * Dedicated (resource-specific)  -> ApiManagementGatewayLlmLog  (preferred)
#   * AzureDiagnostics (legacy)       -> AzureDiagnostics rows w/ *_s columns
# When you flip an existing gateway from legacy to dedicated, the running gateway
# keeps writing to the legacy table for a while before it repoints. We query the
# dedicated table first and transparently fall back to the legacy one, so the demo
# proves the capability regardless of which table currently holds the data.
#
# Each KQL joins every logged request with its response by CorrelationId and keeps
# only the rows for this run's tag. Mirrors the Microsoft-documented auditing query.
KQL_DEDICATED = """
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

KQL_LEGACY = """
AzureDiagnostics
| where Category == "GatewayLlmLogs"
| where TimeGenerated > ago(1h)
| summarize
    ReqJson = take_anyif(requestMessages_s, isnotempty(requestMessages_s)),
    RespJson = take_anyif(responseMessages_s, isnotempty(responseMessages_s)),
    Model = take_anyif(deploymentName_s, isnotempty(deploymentName_s))
    by CorrelationId
| extend RequestArray = parse_json(ReqJson)
| extend ResponseArray = parse_json(RespJson)
| mv-expand RequestArray
| mv-expand ResponseArray
| project CorrelationId, Model,
          RequestContent = tostring(RequestArray.content),
          ResponseContent = tostring(ResponseArray.content)
| summarize
    Input = strcat_array(make_list(RequestContent), " "),
    Output = strcat_array(make_list(ResponseContent), " "),
    Model = any(Model)
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


def _run_query(client: LogsQueryClient, kql: str) -> list:
    query = kql.replace("{tag}", TAG)
    resp = client.query_workspace(WORKSPACE_ID, query, timespan=None)
    if resp.status == LogsQueryStatus.SUCCESS and resp.tables and resp.tables[0].rows:
        return resp.tables[0].rows
    return []


def query_logs(minutes: int = 10) -> tuple[list, str]:
    """Poll both the dedicated and legacy tables until rows show up (or we time out).

    Returns (rows, table_label).
    """
    client = LogsQueryClient(DefaultAzureCredential())
    deadline = time.time() + minutes * 60
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        rows = _run_query(client, KQL_DEDICATED)
        if rows:
            return rows, "ApiManagementGatewayLlmLog (resource-specific)"
        rows = _run_query(client, KQL_LEGACY)
        if rows:
            return rows, "AzureDiagnostics (legacy GatewayLlmLogs)"
        print(f"  ...no rows yet (attempt {attempt}); LLM logs ingest with a delay, retrying in 30s")
        time.sleep(30)
    return [], ""


def main() -> None:
    print(f"LLM logging demo -> Log Analytics workspace {WORKSPACE_ID}")
    print("=" * 60)
    send_traffic()
    print("Querying Log Analytics for the logged prompts and completions...")
    rows, table = query_logs()
    if not rows:
        print("\nNo rows returned yet. Resource-log ingestion to Log Analytics can lag "
              "10-30 min on first enablement; re-run the query later. The KQL used "
              "(resource-specific table):\n")
        print(KQL_DEDICATED.replace("{tag}", TAG))
        return
    print(f"Found {len(rows)} logged call(s) in {table}.")
    for model, inp, out in rows:
        print(f"\n[model] {model or '(n/a)'}")
        print(f"[prompt]     {inp.strip()[:200]}")
        print(f"[completion] {out.strip()[:200]}")
    print("\nEvery governed call is logged with its prompt and completion — auditable "
          "in Log Analytics for billing, debugging, and model evaluation.")


if __name__ == "__main__":
    main()
