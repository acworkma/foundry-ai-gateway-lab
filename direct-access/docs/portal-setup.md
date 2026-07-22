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

> **Why this part:** everything downstream keys off an **Entra-issued token**.
> Part A builds the identity primitives — a resource app to be the token
> *audience*, app *roles* to express entitlements, and *groups/service
> principals* to hold them — so that "who may call which model" becomes a claim
> in a token rather than a network rule or a shared secret.

### A1. Create the resource app (token audience)

> **Why:** this registration represents *the model API itself* as a protected
> resource in Entra. `Expose an API → api://<appId>` defines the **audience**
> APIM validates and the identifier clients request tokens for. It also owns the
> app roles (A2). Without it there is nothing to validate a token *against* and
> no place to declare roles — a token minted for another API couldn't be
> distinguished from a valid one.

1. **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Name: `AIG Direct Model Access`. Supported account types: **Single tenant**.
   Leave redirect URI empty. **Register**.
3. On the app's **Overview**, copy the **Application (client) ID** — this is your
   `<appId>` and the basis of the token audience.
4. **Expose an API** → next to *Application ID URI* click **Add** → accept
   `api://<appId>` → **Save**. (This is the `audience` the gateway validates.)

### A2. Define the two app roles

> **Why:** the role *values* (`Model.Coding.Invoke`, `Model.General.Invoke`) are
> exactly what land in the token's `roles` claim and what each API policy
> requires. Defining two separate roles is what lets one gateway grant coding
> access without granting general-model access.

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

> **Why:** the app *registration* is just the definition; role assignments attach
> to its **service principal** (the enterprise app) in this tenant. No service
> principal means nowhere to assign the groups/clients in A5–A6.

Creating the app registration doesn't automatically create its service
principal. **Enterprise applications** → **New application** →
**Create your own application** is the portal path, but the simplest is: after
registration, browse to **Enterprise applications**, search
`AIG Direct Model Access`; if it isn't there, it is created automatically the
first time a role is assigned in the next step.

### A4. Create security groups

> **Why:** groups let you manage entitlements by *membership* instead of
> per-user role grants. Add/remove a developer from `AIG-Coding-Assistants` and
> their coding access follows automatically — no policy or APIM change.

1. **Microsoft Entra ID** → **Groups** → **New group**.
2. Type **Security**, name `AIG-Coding-Assistants`. **Create**.
3. Repeat for `AIG-General-LLM`.
4. Add the developers who should hold each entitlement as **Members**.

### A5. Assign app roles to the groups

> **Why:** this is the actual grant. Until a group is assigned a role on the
> resource app, its members' tokens carry *no* `roles` claim and every call gets
> **403**. This step is what turns "member of a group" into "gets `Model.*.Invoke`
> in the token."

1. **Enterprise applications** → open **AIG Direct Model Access** →
   **Users and groups** → **Add user/group**.
2. **Users and groups**: pick `AIG-Coding-Assistants`.
   **Select a role**: `Coding Models Invoke`. **Assign**.
3. **Add user/group** again: `AIG-General-LLM` → role `General Models Invoke`.

Now every member of a group receives that app role in their token's `roles`
claim when they request a token for `api://<appId>`.

### A6. (Optional) A workload / service-principal client

> **Why:** proves the *non-interactive* path — a CI job or service calling the
> gateway with client credentials, no human sign-in. Same role check applies, so
> it shows the model works for automation, not just users.

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

> **Why this part:** Part A produced tokens; Part B is the **gateway that
> enforces them** and reaches Foundry. It defines where to route
> (backends), the values policies need (named values), the per-model APIs and
> their enforcement (policies), and how access is packaged and metered (products
> + subscriptions).

### B1. Backends

> **Why:** a backend is the *target* APIM forwards to, reached over the APIM
> **managed identity** (account keys are off on Foundry). Two backends because
> chat/completions models and the codex Responses API sit on different Foundry
> endpoints.

1. **API Management** → `aig-acw` → **Backends** → **+ Add**.
2. Backend `foundry-models`: type **Custom URL**, runtime URL
   `https://foundry-acw.services.ai.azure.com/models`. **Create**.
3. Backend `foundry-openai`: runtime URL
   `https://foundry-acw.openai.azure.com/openai/v1`. **Create**.

Both are reached with the APIM **system-assigned managed identity**, which must
hold **Cognitive Services User** on `foundry-acw` (Foundry account →
**Access control (IAM)** → **Add role assignment**).

### B2. Named values

> **Why:** policies reference `{{aad-tenant-id}}` and `{{model-audience}}`
> instead of hardcoding them. Central named values keep the tenant/audience in
> one place, so all three policies stay consistent and are easy to update.

**APIs** area → **Named values** → **+ Add** two values the policies reference:

| Name | Value |
| --- | --- |
| `aad-tenant-id` | your tenant GUID |
| `model-audience` | `api://<appId>` |

### B3. Create each API (HTTP)

> **Why:** each model gets its own API + path so access is scoped per model.
> Separate APIs are what let a product/role grant one model without the others,
> and give each its own operation shape (codex = `/responses`, the rest =
> `/chat/completions`).

For **each** of the three models, **APIs** → **+ Add API** → **HTTP**:

| Display name | Name | API URL suffix | Operation |
| --- | --- | --- | --- |
| Model — gpt-5.3-codex (Coding) | `model-codex` | `codex` | `POST /responses` |
| Model — gpt-5.2 (General) | `model-gpt52` | `gpt52` | `POST /chat/completions` |
| Model — Mistral-Large-3 (General) | `model-mistral` | `mistral` | `POST /chat/completions` |

After creating each API, open it → **Design** → **+ Add operation** and add the
operation from the table (method + URL template).

### B4. Inbound policy per API

> **Why:** this is where enforcement actually happens — the token/role check, the
> managed-identity call to Foundry, and pinning the model server-side. Applied at
> **All operations** (API scope) so it covers the whole API, not one operation.

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

> **Why:** products group APIs into shippable bundles and require a subscription
> key, giving a second, coarse gate (key) layered on top of the Entra role gate.
> Two products mirror the two entitlements: coding vs. general.

**Products** → **+ Add**:

1. `Coding Assistants` — Requires subscription **on**, Requires approval **off**,
   State **Published**. Add API `model-codex`.
2. `General LLM` — same settings. Add APIs `model-gpt52` and `model-mistral`.

### B6. Subscriptions (admin-provisioned keys)

> **Why:** a subscription is what mints the actual **subscription keys** callers
> send. Because there's no developer portal, you provision these centrally so
> keys are issued and tracked by admins rather than self-service.

**Subscriptions** → **+ Add subscription**:

1. `coding-assistants-demo`, scope **Product → Coding Assistants**, State
   **Active**.
2. `general-llm-demo`, scope **Product → General LLM**, State **Active**.

Copy each subscription's primary key (**Show/hide keys**) for the demo. Because
there is no developer portal, you provision these keys centrally rather than
letting developers self-subscribe.

---

## Part C — Test it

> **Why this part:** proves the boundary actually holds — that each identity can
> reach only its allowed model and everything else returns 403 — with a real
> model reply, not just a status code.

Use the [`access_matrix.py`](../demos/access_matrix.py) demo — flip the persona
on the command line to switch identities (no `.env` editing):

```bash
uv run python direct-access/demos/access_matrix.py coding    # Coding Assistants client
uv run python direct-access/demos/access_matrix.py general    # General LLM client
uv run python direct-access/demos/access_matrix.py user       # signed-in user (az login)
```

Allowed calls print the model's actual reply, so you see a real completion — not
just a status code. Or test by hand:

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
