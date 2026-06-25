# Azure AI Foundry setup guide

This guide covers the environment and permissions needed for the current agent examples in this repo.

## Azure resource requirements

You need an Azure AI Foundry project with:
- a project endpoint in the form `https://{resource-name}.services.ai.azure.com/api/projects/{project-name}`
- permissions to create agents and access the target model deployments
- at least one deployed model available to the project

## Model deployment requirements

The scripts assume the deployment names below unless you update the constants:
- `DeepSeek-V3.2`
- `gpt-5.2`
- `Mistral-Large-3`

Make sure the deployment names in your environment match the values used by the scripts.

## Authentication setup

The examples use `DefaultAzureCredential`, which works well for local development with Azure CLI:

```bash
az login
az account set --subscription "your-subscription-id"
```

For production, you can also use a managed identity or service principal.

## Configuration details

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Set the required values:

```bash
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project
MODEL_DEPLOYMENT_NAME=your-deployment-name
```

## Verification steps

1. Confirm authentication:
   ```bash
   uv run python -c "from azure.identity import DefaultAzureCredential; DefaultAzureCredential().get_token('https://management.azure.com/.default')"
   ```

2. Verify project access:
   ```bash
   uv run python -c "from azure.ai.projects import AIProjectClient; from azure.identity import DefaultAzureCredential; client = AIProjectClient(endpoint='YOUR_ENDPOINT', credential=DefaultAzureCredential())"
   ```

3. Check the deployment name in the Azure AI Foundry portal and update the script constants or `.env` if needed.

## Current SDK pattern

This repo uses the current Foundry SDK pattern:
- `AIProjectClient`
- `project.get_openai_client()`
- `responses.create()` with agent references

Install the SDK with:

```bash
uv add azure-ai-projects
```