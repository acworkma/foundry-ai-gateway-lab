import os
from typing import Any

from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

load_dotenv()


def get_project_client() -> AIProjectClient:
    endpoint = os.getenv("PROJECT_ENDPOINT")
    if not endpoint:
        raise RuntimeError("PROJECT_ENDPOINT is required. Set it in your .env file.")

    return AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())


def get_required_setting(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required. Set it in your .env file.")
    return value


def create_agent_version(project_client: AIProjectClient, *, agent_name: str, definition: Any) -> Any:
    return project_client.agents.create_version(agent_name=agent_name, definition=definition)


def create_prompt_agent(
    project_client: AIProjectClient,
    *,
    agent_name: str,
    model_deployment_name: str,
    instructions: str,
) -> Any:
    return create_agent_version(
        project_client,
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=model_deployment_name,
            instructions=instructions,
        ),
    )


def invoke_agent(openai_client: Any, *, agent_name: str, input_text: str, conversation: Any | None = None):
    if conversation is None:
        conversation = openai_client.conversations.create()

    response = openai_client.responses.create(
        conversation=conversation.id,
        extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
        input=input_text,
    )
    return conversation, response
