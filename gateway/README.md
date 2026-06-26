# Storyteller AI Gateway Lab

This lab fronts the GA Foundry **storyteller** workload (three models in
`foundry-acw`) with **Azure API Management** (`aig-acw`) and demonstrates the
[AI gateway capabilities](https://learn.microsoft.com/azure/api-management/genai-gateway-capabilities)
one capability per API. Every demo is a thin Python client that points the
OpenAI SDK at the gateway and sends the storyteller prompt *through* APIM, so the
governing policy is visible in the terminal.

```
client (subscription key) ──HTTPS──▶ APIM aig-acw ──managed identity──▶ Foundry (foundry-acw)
```

* **Client → gateway:** APIM subscription key (`Ocp-Apim-Subscription-Key`).
* **Gateway → Foundry:** the APIM system-assigned **managed identity** (account
  keys are disabled on the hub — keyless by design).

## Capabilities demonstrated

| Capability | APIM policy | API path | Demo | Evidence |
| --- | --- | --- | --- | --- |
| Pass-through fan-out | backend fragment (MI auth) | `/storyteller` | `storyteller_via_gateway.py` | 3 models answer through the gateway |
| Token rate limiting | `llm-token-limit` | `/storyteller-throttled` | `token_limit.py` | 200 → remaining=0 → 429 |
| Token metrics | `llm-emit-token-metric` | `/storyteller` | `token_metrics.py` | `customMetrics` in App Insights, dimensioned by Model |
| Content safety | `llm-content-safety` | `/storyteller-safety` | `content_safety.py` | benign 200, harmful 403 |
| Semantic cache | `llm-semantic-cache-lookup`/`store` | `/storyteller-cache` | `semantic_cache.py` | reworded prompt served from cache (~0.5s vs ~25s) |
| LLM logging | `largeLanguageModel` diagnostic + `GatewayLlmLogs` | `/storyteller` | `logging_dashboard.py` | prompts + completions in `ApiManagementGatewayLlmLog` |
| Custom policy | C# expression (allow-list + headers) | `/storyteller-custom` | `custom_policy.py` | unapproved model blocked 400; governance headers on 200 |

**Out of scope** (single inference backend / not built here): load balancing,
circuit breaker, native scaling, MCP/A2A, developer portal. Noted in the plan.

## Prerequisites

* `az login` with access to subscription `80e91cef-…` (resource group `rg-foundry`).
* The APIM managed identity must have **Cognitive Services User** on `foundry-acw`
  (already granted out-of-band; not in Bicep to avoid `RoleAssignmentExists`).
* `uv` for running the Python demos.

## Supporting resources

* **Azure Managed Redis** `aig-acw-cache-wus2` (Balanced_B0 + RediSearch) in
  **westus2** — RediSearch is required for the semantic-cache vector lookup.
  B0 had no capacity in eastus2/eastus/centralus at build time; westus2 had it.
  The cross-region hop adds a few ms per cache lookup — negligible for a demo.
* **Application Insights** `proj-acw-appinsights-4422` (reused) — token metrics +
  the backing **Log Analytics workspace** for LLM logs.
* **Content Safety** — reuses the `foundry-acw` Cognitive Services endpoint.

## Deploy

Infra is Bicep at resource-group scope (`rg-foundry`). The cache binding and LLM
log routing are wired in the same template.

```powershell
# 1) Provision Azure Managed Redis (slowest resource; separate template).
az deployment group create -g rg-foundry --name aig-redis `
  --template-file gateway/infra/redis-managed.bicep

$redisHost = az redisenterprise show -g rg-foundry -n aig-acw-cache-wus2 --query hostName -o tsv
$redisKey  = az redisenterprise database list-keys -g rg-foundry --cluster-name aig-acw-cache-wus2 --query primaryKey -o tsv

# 2) Deploy/refresh the gateway config (APIs, policies, product, diagnostics, cache binding).
az deployment group create -g rg-foundry --name aig-gateway `
  --template-file gateway/infra/main.bicep `
  --parameters appInsightsInstrumentationKey=<instrumentation-key> `
  --parameters redisHostName=$redisHost redisAccessKey=$redisKey redisPort=10000
```

Then capture the demo credentials into a gitignored `.env` at the repo root:

```
GATEWAY_BASE_URL=https://aig-acw.azure-api.net/storyteller
GATEWAY_SUBSCRIPTION_KEY=<storyteller-demo subscription primary key>
LOG_ANALYTICS_WORKSPACE_ID=<workspace customerId GUID>   # for logging_dashboard.py
```

The subscription key comes from the dedicated `storyteller-demo` subscription:

```powershell
az rest --method post `
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/rg-foundry/providers/Microsoft.ApiManagement/service/aig-acw/subscriptions/storyteller-demo/listSecrets?api-version=2023-09-01-preview" `
  --query primaryKey -o tsv
```

## Run the demos

```powershell
uv run python gateway/demos/storyteller_via_gateway.py   # fan-out through the gateway
uv run python gateway/demos/token_limit.py               # 429 + remaining tokens
uv run python gateway/demos/token_metrics.py             # generate metric traffic
uv run python gateway/demos/content_safety.py            # benign 200, harmful 403
uv run python gateway/demos/semantic_cache.py            # miss -> hit -> miss
uv run python gateway/demos/custom_policy.py             # allow-list + governance headers
uv run python gateway/demos/logging_dashboard.py         # logged prompts + completions
```

## Where to look

* **Token metrics** — the App Insights component `proj-acw-appinsights-4422` is
  **workspace-based**, so the metrics land in the Log Analytics workspace as the
  `AppMetrics` table. Run this in the **Log Analytics workspace** query editor (the
  same place as the LLM-log query below):

  ```kusto
  AppMetrics
  | where TimeGenerated > ago(30m)
  | where Name in ('Total Tokens','Prompt Tokens','Completion Tokens')
  | extend Model = tostring(Properties['Model'])
  | summarize Tokens = sum(Sum) by Name, Model
  ```

  > If you instead open the **Application Insights** resource's own *Logs* blade,
  > use the legacy aliases — `customMetrics`, `timestamp`, `name`, `valueSum`,
  > `customDimensions`. Those names resolve *only* in the App Insights Logs
  > experience; the Log Analytics workspace editor (shown above) exposes the
  > strongly-typed `AppMetrics` schema instead.

* **LLM logs (prompts + completions)** — Log Analytics `ApiManagementGatewayLlmLog`:

  ```kusto
  ApiManagementGatewayLlmLog
  | extend RequestArray = parse_json(RequestMessages), ResponseArray = parse_json(ResponseMessages)
  | mv-expand RequestArray | mv-expand ResponseArray
  | project CorrelationId,
            RequestContent = tostring(RequestArray.content),
            ResponseContent = tostring(ResponseArray.content)
  | summarize Input = strcat_array(make_list(RequestContent), " "),
              Output = strcat_array(make_list(ResponseContent), " ")
    by CorrelationId
  | where isnotempty(Input) and isnotempty(Output)
  ```

  Resource-log ingestion to Log Analytics can lag 10–30 min the first time the
  `GatewayLlmLogs` category is enabled on the workspace.

  **Which table?** The diagnostic setting uses `logAnalyticsDestinationType:
  'Dedicated'` so records land in the resource-specific `ApiManagementGatewayLlmLog`
  table (the modern, strongly-typed schema). If a gateway is left on the legacy
  default, the same records instead land in `AzureDiagnostics`
  (`Category == "GatewayLlmLogs"`, columns `requestMessages_s` / `responseMessages_s`).
  When you flip an already-running gateway from legacy to dedicated, it keeps
  writing to `AzureDiagnostics` for a while before it repoints, so
  `logging_dashboard.py` queries the dedicated table first and transparently
  falls back to `AzureDiagnostics` — proving the capability either way.

## Layout

```
gateway/
  infra/
    main.bicep            APIs + backends + policies + product/sub + diagnostics + cache binding
    redis-managed.bicep   Azure Managed Redis (Balanced_B0 + RediSearch)
  policies/
    backend-fragment.xml  reusable MI/backend/api-version routing
    base.xml              main API (backend + llm-emit-token-metric)
    token-limit.xml       llm-token-limit
    content-safety.xml    llm-content-safety
    semantic-cache.xml    llm-semantic-cache-lookup/store
    custom-policy.xml      model allow-list + governance headers
  demos/                  one thin Python client per capability
```
