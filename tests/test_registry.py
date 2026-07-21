"""Agent registry tests — no API key required."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from registry.loader import get_agent, list_agents, load_registry


def test_registry_loads():
    reg = load_registry()
    assert "agents" in reg
    assert reg["version"]


def test_required_agents_present():
    names = list_agents()
    for required in ("router", "clarifier", "planner", "query_writer", "verifier", "narrator"):
        assert required in names


def test_get_agent_has_gateway_task_or_null_for_verifier():
    assert get_agent("router")["gateway_task"] == "router"
    assert get_agent("verifier")["gateway_task"] is None
