from foundry_foundation import create_agent_version, get_project_client, invoke_agent
from azure.ai.projects.models import WorkflowAgentDefinition

# Workflow agent configuration
WORKFLOW_AGENT_NAME = "StoryTellerGenerator"
MODEL_DEPLOYMENT_NAME = "gpt-5.2"

# Workflow definition mirrors the StoryTellerGenerator agent deployed in the
# Foundry project: it fans the user prompt out to the GPT, DeepSeek, and Mistral
# prompt agents and streams each reply back as it arrives.
WORKFLOW_DEFINITION = """
kind: workflow
trigger:
  kind: OnConversationStart
  id: trigger_wf
  actions:
    - kind: SetVariable
      id: set_variable_user_prompt
      variable: Local.UserPrompt
      value: =UserMessage(System.LastMessageText)
    - kind: SendActivity
      id: send_activity_progress
      activity: Sending your prompt to GPT, DeepSeek, and Mistral...
    - kind: InvokeAzureAgent
      id: gpt_agent
      description: Invoke the GPT agent
      conversationId: =System.ConversationId
      agent:
        name: agent-gpt
      input:
        messages: =Local.UserPrompt
      output:
        messages: Local.GptReply
        autoSend: false
    - kind: SendActivity
      id: send_activity_gpt
      activity: ="**GPT:**\\n" & Last(Local.GptReply).Text
    - kind: InvokeAzureAgent
      id: deepseek_agent
      description: Invoke the DeepSeek agent
      conversationId: =System.ConversationId
      agent:
        name: agent-deepseek
      input:
        messages: =Local.UserPrompt
      output:
        messages: Local.DeepseekReply
        autoSend: false
    - kind: SendActivity
      id: send_activity_deepseek
      activity: ="**DeepSeek:**\\n" & Last(Local.DeepseekReply).Text
    - kind: InvokeAzureAgent
      id: mistral_agent
      description: Invoke the Mistral agent
      conversationId: =System.ConversationId
      agent:
        name: agent-mistral
      input:
        messages: =Local.UserPrompt
      output:
        messages: Local.MistralReply
        autoSend: false
    - kind: SendActivity
      id: send_activity_mistral
      activity: ="**Mistral:**\\n" & Last(Local.MistralReply).Text
name: StoryTellerGenerator
"""


def main() -> None:
    # Workflow agents are currently a Foundry preview feature
    # (WorkflowAgents=V1Preview), so the client must opt into preview.
    project_client = get_project_client(allow_preview=True)
    print(f"Using MODEL_DEPLOYMENT_NAME: {MODEL_DEPLOYMENT_NAME}")

    workflow_agent = create_agent_version(
        project_client,
        agent_name=WORKFLOW_AGENT_NAME,
        definition=WorkflowAgentDefinition(workflow=WORKFLOW_DEFINITION),
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
    print("\n🎯 StoryTellerGenerator Response:")
    print("=" * 60)
    print(response.output_text)
    print("=" * 60)


if __name__ == "__main__":
    main()
