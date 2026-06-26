from foundry_foundation import create_agent_version, get_project_client
from azure.ai.projects.models import WorkflowAgentDefinition

# Workflow agent configuration
WORKFLOW_AGENT_NAME = "StoryTellerGenerator"
MODEL_DEPLOYMENT_NAME = "gpt-5.2"

# Workflow definition for the StoryTellerGenerator agent: it fans the user
# prompt out to the GPT, DeepSeek, and Mistral prompt agents and streams each
# reply back as it arrives.
#
# Each agent reply is emitted with `autoSend: true` so the real model output
# streams directly to the caller. A plain-text SendActivity label precedes each
# agent so the three replies are easy to tell apart. (Power Fx expression
# activities such as `="**GPT:**" & Last(Local.GptReply).Text` are NOT evaluated
# by the current workflow runtime -- they stream back as the raw formula text --
# so we rely on autoSend plus literal labels instead.)
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
      activity: "Sending your prompt to GPT, DeepSeek, and Mistral..."
    - kind: SendActivity
      id: send_activity_label_gpt
      activity: "**GPT**"
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
        autoSend: true
    - kind: SendActivity
      id: send_activity_label_deepseek
      activity: "**DeepSeek**"
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
        autoSend: true
    - kind: SendActivity
      id: send_activity_label_mistral
      activity: "**Mistral**"
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
        autoSend: true
name: StoryTellerGenerator
"""


def stream_workflow(openai_client, *, agent_name, input_text):
    """Stream a workflow response, separating each emitted message block.

    The workflow emits the progress note, each agent label, and each agent
    reply as distinct output items. We insert a blank line whenever a new item
    starts so the streamed output stays readable.
    """
    conversation = openai_client.conversations.create()
    stream = openai_client.responses.create(
        conversation=conversation.id,
        extra_body={"agent_reference": {"name": agent_name, "type": "agent_reference"}},
        input=input_text,
        stream=True,
    )

    current_item = None
    for event in stream:
        if getattr(event, "type", "") != "response.output_text.delta":
            continue
        item_id = getattr(event, "item_id", None)
        if item_id != current_item:
            if current_item is not None:
                print("\n")
            current_item = item_id
        print(getattr(event, "delta", "") or "", end="", flush=True)
    print()
    return conversation


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
    print("\n🎯 StoryTellerGenerator Response:")
    print("=" * 60)
    conversation = stream_workflow(
        openai_client,
        agent_name=workflow_agent.name,
        input_text="Tell me a story about a time-traveling librarian who discovers a book that writes itself",
    )
    print("=" * 60)
    print(f"Workflow conversation: {conversation.id}")


if __name__ == "__main__":
    main()
