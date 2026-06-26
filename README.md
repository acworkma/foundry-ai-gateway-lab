# Azure AI Foundry Quickstart

This repository demonstrates a modern Azure AI Foundry quickstart using the current `azure-ai-projects` SDK and the new Foundry agent experience. It keeps the original storytelling demos while moving the implementation behind a shared foundation module so it is easier to extend later. It also includes an [AI Gateway Lab](#ai-gateway-lab) that fronts the same workload with Azure API Management to demonstrate the Azure AI gateway capabilities.

## Prerequisites

- Python 3.11+
- Azure CLI installed and authenticated
- An Azure AI Foundry project with access to deployed models
- A model deployment name that matches the scripts you want to run

## Quick setup

1. Install dependencies with uv:
   ```bash
   uv sync
   ```

2. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Fill in your `PROJECT_ENDPOINT` and any deployment names you plan to use.

3. Run the examples:
   ```bash
   uv run python agents/agent-deepseek.py
   uv run python agents/agent-gpt.py
   uv run python agents/agent-mistral.py
   uv run python agents/workflow-agent.py
   ```

## Project structure

- `agents/` - Foundry agent scripts and shared helpers
  - `agents/agent-deepseek.py` / `agents/agent-gpt.py` / `agents/agent-mistral.py` - Prompt agent demos for different model deployments
  - `agents/workflow-agent.py` - Workflow agent that creates/updates the `StoryTellerGenerator` workflow (fans the prompt out to the three prompt agents)
  - `agents/foundry_foundation.py` - Shared client setup, agent creation, and agent invocation helpers
- `gateway/` - APIM AI-gateway lab (policies, Bicep, and demos) — see [AI Gateway Lab](#ai-gateway-lab) and [gateway/README.md](gateway/README.md)
- `tests/` - Offline unit tests
- `pyproject.toml` / `uv.lock` - Dependency configuration
- `.env.example` - Environment template

## AI Gateway Lab

The `gateway/` folder is a self-contained lab that fronts the storyteller workload
with **Azure API Management** to demonstrate the
[Azure AI gateway capabilities](https://learn.microsoft.com/azure/api-management/genai-gateway-capabilities),
one capability per API. Clients point the OpenAI SDK at APIM (subscription key),
and APIM reaches Foundry with its managed identity — so every governing policy is
visible in the terminal.

| Capability | Demo | Evidence |
| --- | --- | --- |
| Pass-through fan-out | `storyteller_via_gateway.py` | 3 models answer through the gateway |
| Token rate limiting | `token_limit.py` | 200 → remaining=0 → 429 |
| Token metrics | `token_metrics.py` | `customMetrics` in App Insights, dimensioned by Model |
| Content safety | `content_safety.py` | benign 200, harmful 403 |
| Semantic cache | `semantic_cache.py` | reworded prompt served from cache (~0.5s vs ~25s) |
| LLM logging | `logging_dashboard.py` | prompts + completions in `ApiManagementGatewayLlmLog` |
| Custom policy | `custom_policy.py` | unapproved model blocked 400; governance headers on 200 |

**Full walkthrough — deploy, run, and verify each capability — is in
[gateway/README.md](gateway/README.md).** It covers the Bicep deployment, the
`.env` the demos expect, the seven `uv run python gateway/demos/*.py` commands,
and the KQL queries that surface the evidence in App Insights and Log Analytics.

## Key dependencies

- `azure-ai-projects>=2.0.0,<3.0.0`
- `azure-identity>=1.25.1`
- `openai>=2.15.0`
- `python-dotenv>=1.2.1`

## Notes

- The scripts use `AIProjectClient`, `get_openai_client()`, and `responses.create()` with an `agent_reference` in `extra_body`.
- Prompt agents (`agent-deepseek`, `agent-gpt`, `agent-mistral`) use the GA agent surface (`agents.create_version`).
- The workflow agent (`StoryTellerGenerator` in `agents/workflow-agent.py`) uses a **preview** feature (`WorkflowAgents=V1Preview`); its script opts in via `get_project_client(allow_preview=True)`.
- The repo no longer assumes prerelease-only tooling; the setup is written for the current SDK experience.
- Agents created by the examples should appear in the Azure AI Foundry portal when your environment is configured correctly.

## Testing

Offline unit tests (no Azure access required) guard the foundation helpers and
the workflow definition structure. Install the dev dependencies and run them
with:

```bash
uv sync
uv run pytest
```

The suite checks env-var handling, the `agent_reference` request payload, and
that the `StoryTellerGenerator` workflow keeps `autoSend` on each agent with no
unevaluated Power Fx `SendActivity` formulas. Live end-to-end runs against a
real Foundry project are exercised by running the agent scripts directly.

## Next steps

- See [AZURE_SETUP.md](AZURE_SETUP.md) for environment and permission guidance
- See [USAGE.md](USAGE.md) for the repo’s supported usage patterns
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues

## Authentication

This project uses `DefaultAzureCredential`. Sign in with Azure CLI before running the scripts:

```bash
az login
```
