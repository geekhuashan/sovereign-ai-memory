from .base import Adapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .grok import GrokAdapter


ADAPTERS: dict[str, Adapter] = {
    "codex": CodexAdapter(),
    "claude": ClaudeAdapter(),
    "grok": GrokAdapter(),
}

__all__ = ["ADAPTERS", "Adapter", "ClaudeAdapter", "CodexAdapter", "GrokAdapter"]
