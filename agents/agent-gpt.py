from foundry_foundation import create_prompt_agent, get_project_client, invoke_agent

# GPT-specific configuration
MODEL_DEPLOYMENT_NAME = "gpt-5.2"
AGENT_NAME = "agent-gpt"
INSTRUCTIONS = "You are a storytelling agent. You craft engaging one-line stories based on user prompts and context."


def main() -> None:
    project_client = get_project_client()
    print(f"Using MODEL_DEPLOYMENT_NAME: {MODEL_DEPLOYMENT_NAME}")

    agent = create_prompt_agent(
        project_client,
        agent_name=AGENT_NAME,
        model_deployment_name=MODEL_DEPLOYMENT_NAME,
        instructions=INSTRUCTIONS,
    )
    print(f"Foundry Agent created (id: {agent.id}, name: {agent.name}, version: {agent.version})")

    openai_client = project_client.get_openai_client()
    conversation, response = invoke_agent(
        openai_client,
        agent_name=agent.name,
        input_text="Explain the evolution from GPT-4 to GPT-5.2 and what new capabilities it brings.",
    )
    print(f"Created conversation (id: {conversation.id})")
    print(f"Response output: {response.output_text}")
    print(f"\n✨ Foundry Agent {agent.name} should now appear in the Microsoft Foundry portal!")


if __name__ == "__main__":
    main()