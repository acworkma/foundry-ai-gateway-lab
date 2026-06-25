import asyncio

from foundry_foundation import create_agent_version, get_project_client, invoke_agent
from azure.ai.projects.models import WorkflowAgentDefinition

# Coordinator agent configuration
AGENT_NAME = "agent-coordinator"
MODEL_DEPLOYMENT_NAME = "gpt-5.2"  # Use GPT for orchestration

# Target agents to coordinate
TARGET_AGENTS = [
    {"name": "agent-deepseek", "model": "DeepSeek-V3.2"},
    {"name": "agent-gpt", "model": "gpt-5.2"},
    {"name": "agent-mistral", "model": "Mistral-Large-3"},
]


def main() -> None:
    project_client = get_project_client()
    print(f"Using MODEL_DEPLOYMENT_NAME: {MODEL_DEPLOYMENT_NAME}")

    coordinator_agent = create_agent_version(
        project_client,
        agent_name=AGENT_NAME,
        definition=WorkflowAgentDefinition(
            workflow="""
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
""",
        ),
    )
    print(f"Foundry Coordinator Agent created (id: {coordinator_agent.id}, name: {coordinator_agent.name}, version: {coordinator_agent.version})")

    openai_client = project_client.get_openai_client()

    async def call_agent_async(agent_info, user_input, timeout=30):
        """Call a specific agent asynchronously with error handling."""
        try:
            print(f"Calling {agent_info['name']}...")
            conversation, response = invoke_agent(
                openai_client,
                agent_name=agent_info["name"],
                input_text=user_input,
            )
            return {
                "agent": agent_info["name"],
                "model": agent_info["model"],
                "response": response.output_text,
                "status": "success",
                "conversation_id": conversation.id,
            }
        except Exception as exc:
            return {
                "agent": agent_info["name"],
                "model": agent_info["model"],
                "response": f"Sorry, {agent_info['name']} is currently unavailable. Error: {exc}",
                "status": "error",
            }

    def call_agent_sync(agent_info, user_input):
        """Synchronous fallback for calling agents."""
        try:
            print(f"Calling {agent_info['name']} (sync)...")
            conversation, response = invoke_agent(
                openai_client,
                agent_name=agent_info["name"],
                input_text=user_input,
            )
            return {
                "agent": agent_info["name"],
                "model": agent_info["model"],
                "response": response.output_text,
                "status": "success",
                "conversation_id": conversation.id,
            }
        except Exception as exc:
            return {
                "agent": agent_info["name"],
                "model": agent_info["model"],
                "response": f"Sorry, {agent_info['name']} is currently unavailable. Error: {exc}",
                "status": "error",
            }

    async def orchestrate_agents_parallel(user_input):
        """Try parallel execution first."""
        try:
            print("Attempting parallel execution...")
            tasks = [call_agent_async(agent, user_input) for agent in TARGET_AGENTS]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            processed_results = []
            for index, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "agent": TARGET_AGENTS[index]["name"],
                        "model": TARGET_AGENTS[index]["model"],
                        "response": f"Sorry, {TARGET_AGENTS[index]['name']} failed during parallel execution.",
                        "status": "error",
                    })
                else:
                    processed_results.append(result)

            return processed_results
        except Exception as exc:
            print(f"Parallel execution failed: {exc}")
            return None

    def orchestrate_agents_sequential(user_input):
        """Sequential fallback execution."""
        print("Using sequential execution...")
        results = []
        for agent in TARGET_AGENTS:
            result = call_agent_sync(agent, user_input)
            results.append(result)
        return results

    def format_responses_side_by_side(results):
        """Format agent responses in side-by-side layout."""
        output = "\n" + "=" * 80 + "\n"
        output += "🤖 MULTI-AGENT STORYTELLING RESPONSES\n"
        output += "=" * 80 + "\n\n"

        for result in results:
            status_emoji = "✅" if result["status"] == "success" else "❌"
            output += f"{status_emoji} {result['agent'].upper()} ({result['model']})\n"
            output += "-" * 60 + "\n"
            output += f"{result['response']}\n\n"

        output += "=" * 80 + "\n"
        return output

    async def run_coordinator_workflow():
        user_input = "Tell me a story about a robot who dreams of becoming a chef"

        print(f"🚀 Starting multi-agent orchestration for: '{user_input}'")

        results = await orchestrate_agents_parallel(user_input)
        if results is None:
            results = orchestrate_agents_sequential(user_input)

        formatted_output = format_responses_side_by_side(results)
        print(formatted_output)

        coordinator_conversation, coordinator_response = invoke_agent(
            openai_client,
            agent_name=coordinator_agent.name,
            input_text=f"Summarize this multi-agent coordination result: {formatted_output}",
        )

        print("🎯 Coordinator Summary:")
        print("-" * 40)
        print(coordinator_response.output_text)
        print(f"Coordinator conversation id: {coordinator_conversation.id}")
        return results

    results = asyncio.run(run_coordinator_workflow())
    print("\n✨ Multi-agent workflow completed! All agents should appear in the Microsoft Foundry portal.")
    print(f"📊 Coordination Results: {len([r for r in results if r['status'] == 'success'])}/{len(results)} agents responded successfully")


if __name__ == "__main__":
    main()
