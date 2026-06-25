"""Offline structural tests for the StoryTellerGenerator workflow definition.

These guard the fixes made when reconciling the workflow to GA behavior:
  * the three sub-agents are invoked with autoSend so their real replies stream;
  * no SendActivity uses a Power Fx expression formula (leading '='), which the
    workflow runtime does NOT evaluate -- it streams the raw formula text.
"""

import yaml


def _actions(definition):
    return definition["trigger"]["actions"]


def test_workflow_yaml_parses_and_is_named(workflow_module):
    definition = yaml.safe_load(workflow_module.WORKFLOW_DEFINITION)
    assert definition["kind"] == "workflow"
    assert definition["name"] == "StoryTellerGenerator"
    assert workflow_module.WORKFLOW_AGENT_NAME == "StoryTellerGenerator"


def test_invokes_three_agents_with_autosend(workflow_module):
    definition = yaml.safe_load(workflow_module.WORKFLOW_DEFINITION)
    invokes = [a for a in _actions(definition) if a["kind"] == "InvokeAzureAgent"]

    names = {a["agent"]["name"] for a in invokes}
    assert names == {"agent-gpt", "agent-deepseek", "agent-mistral"}

    for action in invokes:
        assert action["output"]["autoSend"] is True


def test_no_unevaluated_sendactivity_formulas(workflow_module):
    definition = yaml.safe_load(workflow_module.WORKFLOW_DEFINITION)
    for action in _actions(definition):
        if action["kind"] == "SendActivity":
            activity = str(action["activity"])
            assert not activity.startswith("="), (
                f"SendActivity '{action.get('id')}' uses a Power Fx formula that "
                "the workflow runtime will not evaluate"
            )


class _CapturingResponses:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return iter(())  # no streamed events


class _CapturingConversations:
    def create(self):
        return type("Conversation", (), {"id": "conv_stream"})()


class _CapturingClient:
    def __init__(self):
        self.conversations = _CapturingConversations()
        self.responses = _CapturingResponses()


def test_stream_workflow_builds_streaming_agent_reference(workflow_module):
    client = _CapturingClient()

    conversation = workflow_module.stream_workflow(
        client, agent_name="StoryTellerGenerator", input_text="hi"
    )

    assert client.responses.kwargs["stream"] is True
    assert client.responses.kwargs["extra_body"] == {
        "agent_reference": {"name": "StoryTellerGenerator", "type": "agent_reference"}
    }
    assert conversation.id == "conv_stream"
