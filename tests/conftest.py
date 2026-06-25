import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(file_name: str, module_name: str):
    """Load a repo script that has a hyphenated, non-importable filename."""
    spec = importlib.util.spec_from_file_location(module_name, REPO_ROOT / file_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def workflow_module():
    return _load_module("workflow-agent.py", "workflow_agent")
