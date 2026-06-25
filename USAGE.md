# Agent usage guide

This project demonstrates a few practical patterns for working with Azure AI Foundry agents using the current `azure-ai-projects` SDK.

## Shared foundation

The repo now centralizes the common setup in `foundry_foundation.py`:

```python
from foundry_foundation import create_prompt_agent, get_project_client, invoke_agent

project_client = get_project_client()
agent = create_prompt_agent(
    project_client,
    agent_name="agent-demo",
    model_deployment_name="gpt-4o-mini",
    instructions="You are a helpful assistant.",
)

openai_client = project_client.get_openai_client()
conversation, response = invoke_agent(
    openai_client,
    agent_name=agent.name,
    input_text="Hello from Foundry",
)
```

## Supported entry points

### Prompt agent demos

Each model-specific script follows the same pattern:

- `agent-deepseek.py`
- `agent-gpt.py`
- `agent-mistral.py`

They create a prompt agent with a hardcoded `MODEL_DEPLOYMENT_NAME` and immediately call it through the project’s OpenAI client.

### Multi-agent coordinator

`agent-coordinator.py` demonstrates calling several agents and combining their responses in a single flow.

### Workflow-style example

`workflow-agent.py` shows the same concept using a workflow definition object and the agent service’s workflow-capable agent type.

## Environment configuration

Set the following values in `.env`:

```bash
PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project
MODEL_DEPLOYMENT_NAME=your-model-deployment
```

## Model deployment expectations

The scripts use the deployment names below by default:

- `DeepSeek-V3.2`
- `gpt-5.2`
- `Mistral-Large-3`

Update the constants in the scripts if your Foundry project uses different deployment names.

## Authentication

The examples use `DefaultAzureCredential`, so the following is usually enough for local development:

```bash
az login
```