import os

from foundry_foundation import create_agent_version, get_project_client, invoke_agent
from azure.ai.projects.models import WorkflowAgentDefinition

# Workflow agent configuration
WORKFLOW_AGENT_NAME = "story-teller-multi-agent-workflow"
MODEL_DEPLOYMENT_NAME = "gpt-5.2"


def main() -> None:
    project_client = get_project_client()
    print(f"Using MODEL_DEPLOYMENT_NAME: {MODEL_DEPLOYMENT_NAME}")

    workflow_definition = """
kind: workflow
trigger:
  kind: OnConversationStart
  id: story_teller_multi_agent_workflow
  actions:
    - kind: SetVariable
      id: set_user_prompt
      variable: Local.UserPrompt
      value: =UserMessage(System.LastMessageText)
    - kind: InvokeAzureAgent
      id: deepseek_storyteller
      description: DeepSeek creates a story
      agent:
        name: agent-deepseek
      input:
        messages: =Local.UserPrompt
      output:
        messages: Local.DeepSeekStory
    - kind: InvokeAzureAgent
      id: gpt_storyteller
      description: GPT creates a story
      agent:
        name: agent-gpt
      input:
        messages: =Local.UserPrompt
      output:
        messages: Local.GPTStory
    - kind: InvokeAzureAgent
      id: mistral_storyteller
      description: Mistral creates a story
      agent:
        name: agent-mistral
      input:
        messages: =Local.UserPrompt
      output:
        messages: Local.MistralStory
    - kind: SendActivity
      id: send_results_summary
      activity: "🎯 Multi-Agent Storytelling Results - All three agents have completed their stories"
    - kind: SendActivity
      id: send_deepseek_story
      activity: "🔷 DeepSeek: {Last(Local.DeepSeekStory).Text}"
    - kind: SendActivity
      id: send_gpt_story
      activity: "🟢 GPT: {Last(Local.GPTStory).Text}"
    - kind: SendActivity
      id: send_mistral_story
      activity: "🔶 Mistral: {Last(Local.MistralStory).Text}"
    - kind: EndConversation
      id: end_workflow
name: story-teller-multi-agent-workflow
"""

    workflow_agent = create_agent_version(
        project_client,
        agent_name=WORKFLOW_AGENT_NAME,
        definition=WorkflowAgentDefinition(workflow=workflow_definition),
    )
    print("✅ Foundry Workflow Agent created!")
    print(f"   ID: {workflow_agent.id}")
    print(f"   Name: {workflow_agent.name}")
    print(f"   Version: {workflow_agent.version}")

    openai_client = project_client.get_openai_client()
    conversation, response = invoke_agent(
        openai_client,
        agent_name=workflow_agent.name,
        input_text="Tell me a story about a time-traveling librarian who discovers a book that writes itself",
    )
    print(f"Created workflow conversation: {conversation.id}")
    print("\n🎯 Workflow Response:")
    print("=" * 60)
    print(response.output_text)
    print("=" * 60)


if __name__ == "__main__":
    main()
