"""Agent registry loader — versioned JSON, build-time discovery (architecture.md §6)."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "agent_registry.json")


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_agent(name: str) -> dict[str, Any]:
    reg = load_registry()
    agents = reg.get("agents", {})
    if name not in agents:
        raise KeyError(f"Agent '{name}' not in registry. Known: {list(agents)}")
    entry = dict(agents[name])
    entry["name"] = name
    entry["registry_version"] = reg.get("version")
    return entry


def list_agents() -> list[str]:
    return sorted(load_registry().get("agents", {}).keys())
