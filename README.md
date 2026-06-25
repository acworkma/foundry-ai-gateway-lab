# Azure AI Foundry Quickstart

This repository demonstrates a modern Azure AI Foundry quickstart using the current `azure-ai-projects` SDK and the new Foundry agent experience. It keeps the original storytelling demos while moving the implementation behind a shared foundation module so it is easier to extend later.

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
   uv run python agent-deepseek.py
   uv run python agent-gpt.py
   uv run python agent-mistral.py
   uv run python agent-coordinator.py
   uv run python workflow-agent.py
   ```

## Project structure

- `agent-deepseek.py` / `agent-gpt.py` / `agent-mistral.py` - Prompt agent demos for different model deployments
- `agent-coordinator.py` - Multi-agent orchestration example
- `workflow-agent.py` - Workflow-style agent example
- `foundry_foundation.py` - Shared client setup, agent creation, and agent invocation helpers
- `pyproject.toml` / `uv.lock` - Dependency configuration
- `.env.example` - Environment template

## Key dependencies

- `azure-ai-projects>=2.0.0,<3.0.0`
- `azure-identity>=1.25.1`
- `openai>=2.15.0`
- `python-dotenv>=1.2.1`

## Notes

- The scripts use `AIProjectClient`, `get_openai_client()`, and `responses.create()` with agent references.
- The repo no longer assumes prerelease-only tooling; the setup is written for the current SDK experience.
- Agents created by the examples should appear in the Azure AI Foundry portal when your environment is configured correctly.

## Next steps

- See [AZURE_SETUP.md](AZURE_SETUP.md) for environment and permission guidance
- See [USAGE.md](USAGE.md) for the repo’s supported usage patterns
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues

## Authentication

This project uses `DefaultAzureCredential`. Sign in with Azure CLI before running the scripts:

```bash
az login
```
