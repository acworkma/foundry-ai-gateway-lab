# Direct Access Lab — per-model access control through APIM

This lab exposes three Foundry models **directly** (no agent in front) as
individual APIs on the existing `aig-acw` API Management instance, and controls
**which developers and workloads can call which model** using **Entra ID app
roles**. It is designed for regulated environments that want hard access
boundaries **without** a developer portal or self-service subscriptions.

## What it demonstrates

- **Direct model access** — clients call OpenAI-compatible endpoints straight
  through APIM to Foundry (managed-identity auth to the backend, so no model
  keys leave the gateway).
- **Group / role-based access** — each model API requires a specific Entra app
  role. `validate-azure-ad-token` rejects callers without it (HTTP 403).
- **Two personas** bundled as APIM products:

  | Product | API (gateway path) | Model | Required app role |
  | --- | --- | --- | --- |
  | Coding Assistants | `POST /codex/responses` | gpt-5.3-codex | `Model.Coding.Invoke` |
  | General LLM | `POST /gpt52/chat/completions` | gpt-5.2 | `Model.General.Invoke` |
  | General LLM | `POST /mistral/chat/completions` | Mistral-Large-3 | `Model.General.Invoke` |

- **Model pinning** — each API forces its `model` field server-side, so a
  coding-scoped key cannot be repurposed to call a general model by editing the
  body.

> **Why gpt-5.3-codex uses `/responses`:** gpt-5.3-codex is served by the Azure
> OpenAI **Responses API**, not the generic model-inference `chat/completions`
> route (that route returns *"The requested operation is unsupported."* for it).
> So the Codex API is a Responses endpoint (`{"input": "..."}`), while gpt-5.2
> and Mistral use chat/completions (`{"messages": [...]}`). The access-control
> layer is identical either way.

## How access is enforced (and why no developer portal)

APIM's built-in **groups** and **subscription approval** are developer-portal
self-service constructs. In a regulated setup with no portal, they don't carry
the access decision. Instead:

- **Products + subscriptions** provide the API bundle and a metering key. Keys
  are **admin-provisioned**, not self-service.
- **Entra app roles** are the real runtime identity boundary, checked at the
  gateway on every call — no portal required.
- App roles are granted to **security groups** (for interactive developers) and
  to **service principals** (for workloads). Microsoft's recommended pattern is
  app roles for *both*, because the `roles` claim avoids the group-overage and
  directory-scoping pitfalls of raw `groups` claims.

```
Developer (in AIG-Coding-Assistants group)  ─┐
Workload SP (assigned Model.Coding.Invoke)  ─┼─► Entra token (roles: Model.Coding.Invoke)
                                              │
                                              ▼
        APIM /codex  ──validate-azure-ad-token (audience + roles)──► 200 or 403
                     ──force model = gpt-5.3-codex──► Foundry (managed identity)
```

## Entra identity foundation

The lab needs one **resource app** (the token audience, exposing the app roles),
two **security groups**, and — for a fully scriptable demo — **service-principal
clients**. Create them once:

```bash
# 1. Resource app with two app roles (User + Application member types).
#    App roles need stable GUIDs; generate them and pass an app-roles manifest.
az ad app create --display-name "AIG Direct Model Access" \
  --sign-in-audience AzureADMyOrg \
  --app-roles @approles.json
# then set the identifier URI so tokens can target it as an audience:
az ad app update --id <appId> --identifier-uris "api://<appId>"
az ad sp create --id <appId>          # enterprise app (resource SP)

# 2. Security groups for interactive developers.
az ad group create --display-name "AIG-Coding-Assistants" --mail-nickname "AIG-Coding-Assistants"
az ad group create --display-name "AIG-General-LLM"        --mail-nickname "AIG-General-LLM"

# 3. Assign each app role to its group (Graph appRoleAssignedTo on the resource SP):
#    principalId = groupId, resourceId = resourceSpId, appRoleId = the role's GUID.
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/<resourceSpId>/appRoleAssignedTo" \
  --headers "Content-Type=application/json" \
  --body '{"principalId":"<groupId>","resourceId":"<resourceSpId>","appRoleId":"<roleId>"}'
```

`approles.json` (member types allow both users **and** applications):

```json
[
  { "allowedMemberTypes": ["User","Application"], "displayName": "Coding Models Invoke",
    "description": "Invoke the coding models (gpt-5.3-codex).", "isEnabled": true,
    "value": "Model.Coding.Invoke", "id": "<generate-a-guid>" },
  { "allowedMemberTypes": ["User","Application"], "displayName": "General Models Invoke",
    "description": "Invoke the general models (gpt-5.2, Mistral-Large-3).", "isEnabled": true,
    "value": "Model.General.Invoke", "id": "<generate-a-guid>" }
]
```

For a workload (service-principal) test client, create a client app + secret +
SP and assign it the relevant app role the same way (principalId = the client
SP's object id). The click-by-click portal equivalent is in
[docs/portal-setup.md](docs/portal-setup.md). For a focused tour of just the
gpt-5.3-codex API (including where the managed-identity backend auth lives), see
[docs/portal-codex-walkthrough.md](docs/portal-codex-walkthrough.md).

## Deploy the gateway config (Bicep)

`infra/main.bicep` creates the backends, three APIs (+ operations + policies),
two products, product-API links, and one subscription per product. Point its
`aadTenantId` / `modelAudience` params at the Entra objects above (defaults are
wired to this lab's app):

```bash
az deployment group create \
  --resource-group rg-foundry \
  --name direct-access-lab \
  --template-file direct-access/infra/main.bicep \
  --parameters aadTenantId=<tenantId> modelAudience="api://<resourceAppId>"
```

The APIM system-assigned identity must already hold **Cognitive Services User**
on `foundry-acw` (it does in this environment, because model keys are disabled).

## Configure `.env`

Copy `.env.example` to `.env` and fill in the direct-access block:

```
DIRECT_GATEWAY_BASE_URL=https://aig-acw.azure-api.net
DIRECT_RESOURCE_APP_ID=<resource app id>
DIRECT_TENANT_ID=<tenant id>
DIRECT_CODING_SUB_KEY=<coding-assistants product subscription key>
DIRECT_GENERAL_SUB_KEY=<general-llm product subscription key>
# For the two service-principal personas (both can live here at once — you flip
# between them from the command line, no file editing):
DIRECT_CODING_CLIENT_ID=<coding client app id>
DIRECT_CODING_CLIENT_SECRET=<coding client secret>
DIRECT_GENERAL_CLIENT_ID=<general client app id>
DIRECT_GENERAL_CLIENT_SECRET=<general client secret>
```

Retrieve the product subscription keys with:

```bash
az rest --method POST --uri "https://management.azure.com/subscriptions/<sub>/resourceGroups/rg-foundry/providers/Microsoft.ApiManagement/service/aig-acw/subscriptions/coding-assistants-demo/listSecrets?api-version=2023-09-01-preview" --query primaryKey -o tsv
az rest --method POST --uri "https://management.azure.com/subscriptions/<sub>/resourceGroups/rg-foundry/providers/Microsoft.ApiManagement/service/aig-acw/subscriptions/general-llm-demo/listSecrets?api-version=2023-09-01-preview" --query primaryKey -o tsv
```

## Run the demo

Pick a **persona** on the command line — no `.env` editing to switch identities:

```bash
uv run python direct-access/demos/access_matrix.py coding    # Coding Assistants client
uv run python direct-access/demos/access_matrix.py general    # General LLM client
uv run python direct-access/demos/access_matrix.py user       # signed-in user (az login)
```

| Argument  | Identity used                                   | Carries role         |
| --------- | ----------------------------------------------- | -------------------- |
| `coding`  | `DIRECT_CODING_CLIENT_ID` / `..._SECRET`        | `Model.Coding.Invoke`  |
| `general` | `DIRECT_GENERAL_CLIENT_ID` / `..._SECRET`       | `Model.General.Invoke` |
| `user`    | `DefaultAzureCredential` (signed-in dev)        | via group membership   |
| *(none)*  | legacy `DIRECT_CLIENT_ID`/`SECRET`, else az login | whatever it holds    |

Each run acquires one token, prints the persona and its app roles, then calls
all three APIs. Allowed calls print the model's **actual reply** so you see a
real completion — not just a `200`. Flip `coding` → `general` to watch the
boundary move:

```
$ uv run python direct-access/demos/access_matrix.py coding
Persona:         Coding Assistants
Token app roles: Model.Coding.Invoke
Prompt:          In one short sentence, describe what an Azure API Management AI gateway does.
--------------------------------------------------------------------
  gpt-5.3-codex  (Coding)     requires Model.Coding.Invoke   ->  ALLOWED
      model: gpt-5.3-codex
      reply: An Azure API Management AI gateway is a managed front door that ...
  gpt-5.2        (General)     requires Model.General.Invoke  ->  DENIED   (403 — missing required app role)
  Mistral-Large-3 (General)    requires Model.General.Invoke  ->  DENIED   (403 — missing required app role)
```

```
$ uv run python direct-access/demos/access_matrix.py general
Persona:         General LLM
Token app roles: Model.General.Invoke
--------------------------------------------------------------------
  gpt-5.3-codex  (Coding)     requires Model.Coding.Invoke   ->  DENIED   (403 — missing required app role)
  gpt-5.2        (General)     requires Model.General.Invoke  ->  ALLOWED
      model: gpt-5.2-...
      reply: An AI gateway in Azure API Management sits in front of your models ...
  Mistral-Large-3 (General)    requires Model.General.Invoke  ->  ALLOWED
      model: mistral-large-3
      reply: It is a policy layer that governs, secures, and routes calls to ...
```

### Interactive-user (group) path

A group membership can't be minted non-interactively, so validate it with a
signed-in developer instead of a service principal:

1. Add a test user to `AIG-Coding-Assistants` (or `AIG-General-LLM`).
2. `az login` as that user.
3. Run `access_matrix.py user` — the user's token carries the group's app role
   via `roles`, and the same allow/deny boundary (and real replies) applies.

## Files

```
direct-access/
  README.md                       # this file
  docs/portal-setup.md            # click-by-click portal walkthrough
  docs/portal-codex-walkthrough.md # focused portal tour of the gpt-5.3-codex API
  infra/main.bicep                # backends, APIs, products, subscriptions
  policies/
    backend-fragment.xml          # chat/completions backend (gpt-5.2, Mistral) + MI auth
    responses-backend-fragment.xml# Responses backend (gpt-5.3-codex) + MI auth
    codex.xml                     # /codex — requires Model.Coding.Invoke, forces gpt-5.3-codex
    gpt52.xml                     # /gpt52 — requires Model.General.Invoke, forces gpt-5.2
    mistral.xml                   # /mistral — requires Model.General.Invoke, forces Mistral-Large-3
  demos/
    _client.py                    # token acquisition + gateway call helpers
    access_matrix.py              # allow/deny matrix for the current identity
```
