# Troubleshooting guide

Common issues and fixes for the examples in this repo.

## Environment variables

### KeyError for `PROJECT_ENDPOINT`

Create a `.env` file from the template and fill in your values:

```bash
cp .env.example .env
```

Use a project endpoint in this format:

```bash
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project
```

## Authentication

### `DefaultAzureCredential` fails

Sign in with Azure CLI and confirm the target subscription:

```bash
az login
az account set --subscription "your-subscription-id"
```

## Model deployment issues

### Model deployment not found

The deployment name must match a deployment that is active in your Foundry project. Update the constant in the script or the value in `.env` if necessary.

## SDK compatibility

### Responses API errors

The examples use the current `AIProjectClient` + `get_openai_client()` pattern. If you are seeing `agent_reference` errors, make sure you are using the current Foundry project client and not the classic assistant workflow.

The invocation payload must use `agent_reference` (not the deprecated `agent` property):

```python
response = openai_client.responses.create(
    conversation=conversation.id,
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    input="Your prompt here",
)
```

### `preview_feature_required: WorkflowAgents=V1Preview`

Workflow agents (`agents/workflow-agent.py` / `StoryTellerGenerator`) are a preview feature. Build the project client with preview enabled:

```python
project = get_project_client(allow_preview=True)
```

Prompt agents (`agent-gpt`, `agent-deepseek`, `agent-mistral`) are GA and do not need this.

## Dependency issues

### `uv sync` fails

Try:

```bash
uv cache clean
uv sync
```

If you need to refresh the lockfile after dependency changes:

```bash
uv lock
```