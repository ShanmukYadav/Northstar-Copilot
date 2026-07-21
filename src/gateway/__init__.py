"""LLM gateway: single path for every model call (architecture.md §4)."""
from .client import complete, get_cost_summary, reset_cost_summary
from .cache import ResponseCache

__all__ = ["complete", "get_cost_summary", "reset_cost_summary", "ResponseCache"]
