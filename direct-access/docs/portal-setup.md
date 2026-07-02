# Portal walkthrough — group/role-based model access through APIM

This is a click-by-click guide to doing in the **Azure portal** what
`direct-access/infra/main.bicep` plus the Entra setup do as code: expose Foundry
models directly through API Management and control **which developers and
workloads can call which model** using **Entra ID app roles** — with no
developer portal.

Use this to *demo the setup live* to a customer. The Bicep + `az` commands in
[../README.md](../README.md) remain the source of truth for repeatable deploys;
this page is the guided tour.

> **What you end up with:** three APIs on `https://<apim>.azure-api.net`
> (`/codex/responses`, `/gpt52/chat/completions`, `/mistral/chat/completions`),
> each requiring a specific Entra app role, bundled into two products, and
> forcing its model server-side.

---

## Reference values (this lab)

Swap in your own names where you follow along.

| Thing | Value in this lab |
| --- | --- |
| API Management instance | `aig-acw` (BasicV2, East US 2) |
| Resource group | `rg-foundry` |
| Foundry (AIServices) account | `foundry-acw` |
| Inference endpoint (chat/completions) | `https://foundry-acw.services.ai.azure.com/models` |
| Responses endpoint (codex) | `https://foundry-acw.openai.azure.com/openai/v1` |
| Resource app (token audience) | `AIG Direct Model Access` → `api://<appId>` |
| App roles | `Model.Coding.Invoke`, `Model.General.Invoke` |
| Security groups | `AIG-Coding-Assistants`, `AIG-General-LLM` |
| Products | `Coding Assistants`, `General LLM` |

---

## Part A — Entra ID: the identity boundary

### A1. Create the resource app (token audience)

1. **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Name: `AIG Direct Model Access`. Supported account types: **Single tenant**.
   Leave redirect URI empty. **Register**.
3. On the app's **Overview**, copy the **Application (client) ID** — this is your
   `<appId>` and the basis of the token audience.
4. **Expose an API** → next to *Application ID URI* click **Add** → accept
   `api://<appId>` → **Save**. (This is the `audience` the gateway validates.)

### A2. Define the two app roles

1. Still on the app → **App roles** → **Create app role**.
2. First role:
   - Display name: `Coding Models Invoke`
   - Allowed member types: **Both (Users/Groups + Applications)**
   - Value: `Model.Coding.Invoke`
   - Description: *Invoke the coding models (gpt-5.3-codex).*
   - Enable → **Apply**.
3. Repeat for the second role:
   - Display name: `General Models Invoke`, member types **Both**,
     Value: `Model.General.Invoke`.

> **Why "Both":** the same role is granted to interactive users (via groups) and
> to service-principal workloads. The gateway checks the `roles` claim either
> way, which sidesteps the group-overage/directory-scope issues of raw `groups`
> claims.

### A3. Create the enterprise app (service principal)

Creating the app registration doesn't automatically create its service
principal. **Enterprise applications** → **New application** →
**Create your own application** is the portal path, but the simplest is: after
registration, browse to **Enterprise applications**, search
`AIG Direct Model Access`; if it isn't there, it is created automatically the
first time a role is assigned in the next step.

### A4. Create security groups

1. **Microsoft Entra ID** → **Groups** → **New group**.
2. Type **Security**, name `AIG-Coding-Assistants`. **Create**.
3. Repeat for `AIG-General-LLM`.
4. Add the developers who should hold each entitlement as **Members**.

### A5. Assign app roles to the groups

1. **Enterprise applications** → open **AIG Direct Model Access** →
   **Users and groups** → **Add user/group**.
2. **Users and groups**: pick `AIG-Coding-Assistants`.
   **Select a role**: `Coding Models Invoke`. **Assign**.
3. **Add user/group** again: `AIG-General-LLM` → role `General Models Invoke`.

Now every member of a group receives that app role in their token's `roles`
claim when they request a token for `api://<appId>`.

### A6. (Optional) A workload / service-principal client

To demo the non-interactive path:

1. **App registrations** → **New registration** → `AIG Direct Model Client (Coding)`.
2. **Certificates & secrets** → **New client secret** → copy the value.
3. **Enterprise applications** → **AIG Direct Model Access** →
   **Users and groups** → **Add user/group** → select the client's service
   principal → role `Coding Models Invoke` → **Assign**.

The client requests a token with scope `api://<appId>/.default` (client
credentials) and receives `roles: ["Model.Coding.Invoke"]`.

---

## Part B — API Management: the APIs, products, and policies

### B1. Backends

1. **API Management** → `aig-acw` → **Backends** → **+ Add**.
2. Backend `foundry-models`: type **Custom URL**, runtime URL
   `https://foundry-acw.services.ai.azure.com/models`. **Create**.
3. Backend `foundry-openai`: runtime URL
   `https://foundry-acw.openai.azure.com/openai/v1`. **Create**.

Both are reached with the APIM **system-assigned managed identity**, which must
hold **Cognitive Services User** on `foundry-acw` (Foundry account →
**Access control (IAM)** → **Add role assignment**).

### B2. Named values

**APIs** area → **Named values** → **+ Add** two values the policies reference:

| Name | Value |
| --- | --- |
| `aad-tenant-id` | your tenant GUID |
| `model-audience` | `api://<appId>` |

### B3. Create each API (HTTP)

For **each** of the three models, **APIs** → **+ Add API** → **HTTP**:

| Display name | Name | API URL suffix | Operation |
| --- | --- | --- | --- |
| Model — gpt-5.3-codex (Coding) | `model-codex` | `codex` | `POST /responses` |
| Model — gpt-5.2 (General) | `model-gpt52` | `gpt52` | `POST /chat/completions` |
| Model — Mistral-Large-3 (General) | `model-mistral` | `mistral` | `POST /chat/completions` |

After creating each API, open it → **Design** → **+ Add operation** and add the
operation from the table (method + URL template).

### B4. Inbound policy per API

Open an API → **Design** → select **All operations** → **Inbound processing** →
`</>` (code editor). This is the API-scoped policy (the "All operations" view —
easy to miss). Paste the matching file from `direct-access/policies/`:

- `model-codex` → `codex.xml`
- `model-gpt52` → `gpt52.xml`
- `model-mistral` → `mistral.xml`

Each policy does three things in order:

1. **`validate-azure-ad-token`** — checks tenant, audience `{{model-audience}}`,
   and that the `roles` claim contains the required app role; returns **403**
   otherwise.
2. **backend routing** (via a policy fragment) — `set-backend-service` +
   `authentication-managed-identity` so the call reaches Foundry over the MI.
3. **`set-body`** — overwrites the `model` field so the model is pinned
   server-side.

The two backend fragments (`direct-models-backend`,
`direct-responses-backend`) are created under **APIs** → **Policy fragments** →
**+ Add** (paste `backend-fragment.xml` and `responses-backend-fragment.xml`).

### B5. Products (access bundles)

**Products** → **+ Add**:

1. `Coding Assistants` — Requires subscription **on**, Requires approval **off**,
   State **Published**. Add API `model-codex`.
2. `General LLM` — same settings. Add APIs `model-gpt52` and `model-mistral`.

### B6. Subscriptions (admin-provisioned keys)

**Subscriptions** → **+ Add subscription**:

1. `coding-assistants-demo`, scope **Product → Coding Assistants**, State
   **Active**.
2. `general-llm-demo`, scope **Product → General LLM**, State **Active**.

Copy each subscription's primary key (**Show/hide keys**) for the demo. Because
there is no developer portal, you provision these keys centrally rather than
letting developers self-subscribe.

---

## Part C — Test it

Use the [`access_matrix.py`](../demos/access_matrix.py) demo, or test by hand:

1. Get a token for the identity:
   - Service principal: client-credentials grant, scope
     `api://<appId>/.default`.
   - Interactive user: sign in as a group member and request the same scope.
2. `POST https://aig-acw.azure-api.net/codex/responses`
   - Header `Authorization: Bearer <token>`
   - Header `Ocp-Apim-Subscription-Key: <coding-assistants-demo key>`
   - Body `{"input": "say hi"}`
3. Expected results:

| Identity | `/codex/responses` | `/gpt52/chat/completions` | `/mistral/chat/completions` |
| --- | --- | --- | --- |
| Coding role | **200** | 403 | 403 |
| General role | 403 | **200** | **200** |
| No / wrong token | 403 | 403 | 403 |

---

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `401` before your policy runs | Missing/invalid subscription key | Send `Ocp-Apim-Subscription-Key` for the product that owns the API |
| Always `403` even with the right group | Token was requested for the wrong audience | Request scope `api://<appId>/.default`; confirm `model-audience` named value matches |
| `403` for a brand-new group member | App-role/group assignment not propagated, or user cached an old token | Re-acquire the token (sign out/in); allow a minute for propagation |
| `400 "The requested operation is unsupported"` on codex | Called `/codex/chat/completions` | gpt-5.3-codex is Responses-only — call `/codex/responses` with `{"input": ...}` |
| `500` from backend | APIM MI lacks Foundry access | Grant **Cognitive Services User** to the APIM identity on `foundry-acw` |
| Caller changed `model` in the body but still got the pinned model | Working as designed | `set-body` forces the model; the client's value is ignored |

---

## Portal ↔ Bicep/Entra map

| Portal object | Defined in code |
| --- | --- |
| App registration + app roles | `az ad app create` / portal (see README) |
| Group role assignments | `appRoleAssignedTo` (Graph) / Enterprise app → Users and groups |
| Backends `foundry-models`, `foundry-openai` | `infra/main.bicep` (`backend`, `openaiBackend`) |
| Named values `aad-tenant-id`, `model-audience` | `infra/main.bicep` (`nvTenant`, `nvAudience`) |
| APIs + operations + policies | `infra/main.bicep` (`codexApi`/`gpt52Api`/`mistralApi` …) |
| Policy fragments | `policies/backend-fragment.xml`, `policies/responses-backend-fragment.xml` |
| Products + product-API links | `infra/main.bicep` (`codingProduct`, `generalProduct`, links) |
| Subscriptions | `infra/main.bicep` (`codingSubscription`, `generalSubscription`) |
