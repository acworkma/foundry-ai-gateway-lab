# GitHub Copilot Instructions

## Project Context
This is an Azure AI Foundry project for creating agents using the current Foundry agent experience. The project demonstrates how to create multiple agents with different language models while keeping the demos reusable.

### Dependencies and Installation
- Use the current `azure-ai-projects` package release
- Always use `uv` package manager for dependency management
- Install dependencies with `uv sync`
- Load environment variables with `python-dotenv` and `load_dotenv()`

### Authentication
- Use `DefaultAzureCredential` for Azure authentication
- Requires `PROJECT_ENDPOINT` environment variable
- No API keys are required for local development when Azure identity is available

### Current Microsoft Foundry SDK Patterns
- Use `AIProjectClient` from `azure-ai-projects`
- Get an OpenAI client with `project.get_openai_client()`
- Use `openai_client.responses.create()` for agent calls
- Use the Foundry agent service rather than classic assistant workflows

### Correct Foundry Patterns
```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

project = AIProjectClient(endpoint=os.environ["PROJECT_ENDPOINT"], credential=DefaultAzureCredential())

agent = project.agents.create_version(
    agent_name=AGENT_NAME,
    definition=PromptAgentDefinition(
        model=MODEL_DEPLOYMENT_NAME,
        instructions="You are a storytelling agent.",
    ),
)

openai_client = project.get_openai_client()
response = openai_client.responses.create(
    conversation=conversation.id,
    extra_body={"agent_reference": {"name": agent.name, "type": "agent_reference"}},
    input="Your prompt here",
)
```

### Avoid These Classic Patterns
- Do not use direct `from openai import OpenAI`
- Do not use `client.chat.completions.create()`
- Do not use classic assistant workflows
- Do not use `openai_client.beta.threads.runs.create()`

## File Naming Conventions
- Agent files: `agent-{model}.py` (for example `agent-deepseek.py`)
- Agent names should match file names where practical
- Use hardcoded model deployment names in each agent file
- Environment configuration lives in `.env`

## Model-Specific Configurations
- DeepSeek: `MODEL_DEPLOYMENT_NAME = "DeepSeek-V3.2"`
- GPT: `MODEL_DEPLOYMENT_NAME = "gpt-5.2"`
- Mistral: `MODEL_DEPLOYMENT_NAME = "Mistral-Large-3"`

## Environment Variables
Required in `.env`:
- `PROJECT_ENDPOINT` - Azure AI Foundry project endpoint
- Optional: `MODEL_DEPLOYMENT_NAME`

## Documentation Standards
- Update `README.md` for new entry points or usage changes
- Update `USAGE.md` for new API examples
- Add troubleshooting guidance for new issues
- Keep the docs aligned with the current SDK experience rather than prerelease assumptions

## Important Notes
- Use the current Foundry agent API patterns rather than classic assistant patterns
- Agents appear in the Azure AI Foundry portal after creation
- Test new SDK changes in a development environment before relying on them