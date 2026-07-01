# Portal walkthrough — connect API Management to a Foundry model

This is a click-by-click guide to doing in the **Azure portal** what
`gateway/infra/main.bicep` does as code: stand up an API Management (APIM) API
that fronts a **Microsoft Foundry** model deployment, authenticated with a
**managed identity** (no keys), and layered with the AI gateway policies.

Use this to *demo the setup live* to a customer. The Bicep remains the source of
truth for repeatable deploys; this page is the guided tour.

> **What you end up with:** an APIM API at `https://<apim>.azure-api.net/storyteller`
> that accepts OpenAI-style `POST /chat/completions`, routes to Foundry over the
> APIM managed identity, and emits token metrics per consumer.

---

## Reference values (this lab)

Swap in your own names where you follow along.

| Thing | Value in this lab |
| --- | --- |
| API Management instance | `aig-acw` (BasicV2, East US 2) |
| Resource group | `rg-foundry` |
| Foundry (AIServices) account | `foundry-acw` |
| Inference endpoint | `https://foundry-acw.services.ai.azure.com/models` |
| Models deployed | `gpt-5.2`, `DeepSeek-V3.2`, `Mistral-Large-3` |
| Client compatibility | **Azure AI** (model name travels in the request body) |
| API base path | `storyteller` |
| Backend created | `foundry-inference` |
| Product / subscription | `Storyteller Lab` / `storyteller-demo` |

---

## Prerequisites

- An existing **API Management** instance. (This lab reuses `aig-acw`.)
- A **Foundry** resource with at least one **model deployment**. Confirm in the
  [Foundry portal](https://ai.azure.com) under **Models + endpoints** that your
  models (e.g. `gpt-5.2`) show status **Succeeded**.
- Permission to create role assignments on the Foundry account (needed for the
  managed-identity grant in Step 3), or someone who can do it for you.
- Account keys can be **disabled** on the Foundry account — managed identity is
  the point of this walkthrough, so no keys are required.

---

## Step 1 — Import the Foundry model as an API

1. In the [Azure portal](https://portal.azure.com), open your API Management
   instance (**`aig-acw`**).
2. Left menu → under **APIs**, select **APIs** → **+ Add API**.
3. Under **Create from Azure resource**, select **Microsoft Foundry**.

   > If you don't see the **Microsoft Foundry** tile, your APIM tier or portal
   > build may be older — use **Azure OpenAI Service** for OpenAI-only
   > deployments, or import from the OpenAPI spec. The AI gateway policies in
   > Step 5 apply either way.

4. On the **Select AI Service** tab:
   - Choose the **Subscription** that holds your Foundry account.
   - (Optional) click the **deployments** link next to the service to confirm the
     models you expect are there.
   - Select the Foundry tool (**`foundry-acw`**) → **Next**.

---

## Step 2 — Configure the API

On the **Configure API** tab:

1. **Display name** — `Storyteller LLM (Foundry)`.
2. **Base path** — `storyteller`. This becomes the public suffix:
   `https://aig-acw.azure-api.net/storyteller`.
3. **Products** — associate `Storyteller Lab` (or **Unlimited** while testing) so
   a subscription key exists to call the API.
4. **Client compatibility** — pick the option that matches how clients call:

   | Option | Client calls | Model name goes in | Use when |
   | --- | --- | --- | --- |
   | **Azure OpenAI** | `/openai/deployments/<name>/chat/completions` | the URL path | OpenAI-only deployments |
   | **Azure AI** | `/models/chat/completions` (or `/chat/completions`) | the **request body** (`"model": "..."`) | you want to switch models via the body — **this lab** |
   | **Azure OpenAI v1** | `/openai/v1/<name>/chat/completions` | the request body | OpenAI v1 lifecycle API |

   This lab uses **Azure AI** so one API fronts all three models — the client
   just changes the `model` field in the body.

5. **Next**.

What the wizard just created for you automatically:

- An **operation** for each REST endpoint (e.g. **Chat Completions**,
  `POST /chat/completions`).
- A **backend** resource pointing at the Foundry inference endpoint.
- A `set-backend-service` policy that routes the API to that backend.
- Backend authentication via the APIM **system-assigned managed identity**.

---

## Step 3 — Confirm managed-identity authentication (keyless)

The wizard turns on the APIM **system-assigned identity** and wires it into the
backend. Confirm and grant the data-plane role.

1. **Identity is on:** APIM `aig-acw` → **Security** → **Managed identities** →
   **System assigned** = **On**. Copy the **Object (principal) ID**.
2. **Grant the role on Foundry:** open the Foundry account **`foundry-acw`** →
   **Access control (IAM)** → **+ Add** → **Add role assignment**:
   - Role: **Cognitive Services User**.
   - Assign access to: **Managed identity** → select the APIM instance
     (`aig-acw`).
   - **Review + assign**.

   > CLI equivalent (from `main.bicep`'s note):
   > ```bash
   > az role assignment create --assignee <apim-principalId> \
   >   --role "Cognitive Services User" --scope <foundry-account-id>
   > ```

3. **How the backend authenticates:** APIM `aig-acw` → **APIs** → **Backends** →
   open **`foundry-inference`**. The backend URL is the Foundry `/models`
   endpoint, and requests are authenticated with the managed identity against the
   `https://cognitiveservices.azure.com` resource. In this lab that auth lives in
   a reusable policy fragment (`storyteller-backend`) so every API variant shares
   it:

   ```xml
   <set-backend-service backend-id="foundry-inference" />
   <authentication-managed-identity resource="https://cognitiveservices.azure.com" />
   <set-query-parameter name="api-version" exists-action="override">
       <value>2024-05-01-preview</value>
   </set-query-parameter>
   ```

   The `api-version` line forces the query parameter the inference endpoint
   expects, so clients don't have to send it.

---

## Step 4 — Test the API in the portal

1. APIM `aig-acw` → **APIs** → **Storyteller LLM (Foundry)** → **Test** tab.
2. Select the **Chat Completions** operation.
3. In **Request body**, send a chat completion. With **Azure AI** compatibility
   the model name goes in the body:

   ```json
   {
     "model": "gpt-5.2",
     "messages": [
       { "role": "user", "content": "Tell a short story about a lighthouse." }
     ]
   }
   ```

   > The test console auto-adds an **Ocp-Apim-Subscription-Key** header using the
   > built-in all-access subscription. Click the **eye** icon next to **HTTP
   > Request** to reveal it.

4. **Send.** A successful call returns `200` with the completion **and** a `usage`
   block (prompt/completion/total tokens) — the same token data the metrics
   policy emits in Step 5.
5. Swap `"model": "gpt-5.2"` for `"DeepSeek-V3.2"` or `"Mistral-Large-3"` and send
   again — one API, three models, selected purely by the body.

---

## Step 5 — Layer on AI gateway policies

The import optionally scaffolds token-limit, token-metric, semantic-cache, and
content-safety policies. You can also add or edit them by hand. The
**token-metric** policy is the one to show a customer for observability.

1. APIM `aig-acw` → **APIs** → **Storyteller LLM (Foundry)** → **Design** tab.
2. In the operations list, click **All operations** — this is the **API scope**.

   > **Gotcha:** the Design view opens on a single operation by default. An
   > **API-scoped** policy (which is where this lab puts `llm-emit-token-metric`)
   > only shows under **All operations**, *not* under the Chat Completions
   > operation. If a policy looks "missing," you're probably looking at the
   > operation scope.

3. In **Inbound processing**, click the **`</>`** (code editor) icon. You'll see
   the passthrough + the token-metric policy with its custom dimensions:

   ```xml
   <inbound>
       <base />
       <include-fragment fragment-id="storyteller-backend" />
       <llm-emit-token-metric namespace="StorytellerGateway">
           <dimension name="API ID" />
           <dimension name="Subscription ID" />
           <dimension name="Model" value="@(context.Request.Body.As<JObject>(true)["model"]?.ToString() ?? "unknown")" />
       </llm-emit-token-metric>
   </inbound>
   ```

   - `API ID` and `Subscription ID` are auto-populated dimensions.
   - `Model` is a policy expression that reads the `model` field from the request
     body — that's how per-model token metrics get dimensioned.

4. To emit metrics you must bind APIM to Application Insights: APIM `aig-acw` →
   **Monitoring** → **Application Insights** → add a connection to your component
   (this lab reuses `proj-acw-appinsights-4422`). Metrics take ~2–5 min to
   ingest.

See [gateway/README.md](../README.md) for the other capabilities (token rate
limiting, content safety, semantic cache, LLM logging, custom policy), the KQL to
surface the metrics, and the Python demo for each.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `401`/`403` from the backend | MI role not granted (or still propagating) | Confirm **Cognitive Services User** on `foundry-acw` for the APIM identity; wait a few minutes |
| `401` at the gateway itself | No/invalid subscription key | Send **Ocp-Apim-Subscription-Key**; use a key from a product the API is in |
| `404` / wrong path | Deployment/model name mismatch | With **Azure AI**, the model goes in the **body**, not the URL; check the name matches a real deployment |
| Missing `api-version` error | Endpoint requires the query param | The backend fragment sets `api-version` — confirm the API policy includes the `storyteller-backend` fragment |
| Token metrics never appear | Policy at operation scope / App Insights not connected / ingestion lag | View under **All operations**; connect App Insights; wait ~5 min |
| Policy looks "missing" in Design | Viewing operation scope | Click **All operations** to see API-scoped policies |

---

## Portal ↔ code map

Everything above corresponds to a resource in `gateway/infra/main.bicep`:

| Portal action | Bicep resource |
| --- | --- |
| Import Foundry API | `api` (`storyteller-llm`) + `chatCompletions` operation |
| Backend to Foundry | `backend` (`foundry-inference`) |
| MI auth + api-version | `backendFragment` (`storyteller-backend`) → `backend-fragment.xml` |
| API-scoped inbound policy | `apiPolicy` → `base.xml` |
| Product + subscription | `product` (`storyteller`) + `subscription` (`storyteller-demo`) |
| App Insights logger | `apimLogger` + `apiDiagnostic` |

Re-running the Bicep gives you the same result without the clicks:

```bash
az deployment group create -g rg-foundry --name aig-gateway \
  --template-file gateway/infra/main.bicep \
  --parameters appInsightsInstrumentationKey=<key>
```
