"""Demo: llm-emit-token-metric (per-consumer token metrics → App Insights).

Sends storyteller calls across all three models through the main gateway. The
llm-emit-token-metric policy emits Total/Prompt/Completion token metrics to
Application Insights (proj-acw-appinsights-4422) under the "StorytellerGateway"
namespace, dimensioned by API, Subscription, and Model.

Run:
    uv run python gateway/demos/token_metrics.py

Then inspect in the Log Analytics workspace (the workspace-based App Insights
stores metrics as AppMetrics) — metrics take ~2-5 min to ingest:

    AppMetrics
    | where TimeGenerated > ago(30m)
    | where Name in ('Total Tokens','Prompt Tokens','Completion Tokens')
    | extend Model = tostring(Properties['Model'])
    | summarize Tokens = sum(Sum) by Name, Model
    | order by Model asc

The policy stamps three custom dimensions (Model, API ID, Subscription ID). To
prove per-consumer / per-API attribution, surface all of them:

    AppMetrics
    | where TimeGenerated > ago(30m)
    | where Name == 'Total Tokens'
    | extend Consumer = tostring(Properties['Subscription ID']),
             ApiId    = tostring(Properties['API ID']),
             Model    = tostring(Properties['Model'])
    | summarize Tokens = sum(Sum) by Consumer, ApiId, Model
    | order by Consumer, Model asc
"""

from __future__ import annotations

from _client import MODELS, gateway_client, tell_story

PROMPTS = [
    "Tell a short story about a fox who collects fallen stars.",
    "Tell a short story about a city that floats on music.",
]


def main() -> None:
    client = gateway_client()
    print("Generating governed traffic (metrics emitted to App Insights)\n" + "=" * 60)
    total = 0
    for prompt in PROMPTS:
        for model in MODELS:
            try:
                resp = tell_story(client, model, prompt)
            except Exception as exc:  # noqa: BLE001
                print(f"  {model}: ERROR {exc}")
                continue
            used = resp.usage.total_tokens if resp.usage else 0
            total += used
            print(f"  {model:<16} +{used} tokens")
    print(f"\nEmitted metrics for {len(PROMPTS) * len(MODELS)} calls, "
          f"{total} total tokens.")
    print("Inspect in App Insights with the KQL in this file's docstring "
          "(allow a few minutes for ingestion).")


if __name__ == "__main__":
    main()
