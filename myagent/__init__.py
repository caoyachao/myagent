"""MyAgent 2.0 - Multi-Agent memory-enhanced layer for Kimi Code CLI."""

__version__ = "2.1.0"

from myagent.agent import Agent, AgentManager, get_agent_manager
from myagent.memory import AgentAwareMemoryStore
from myagent.skills import AgentAwareSkillRegistry

__all__ = [
    "__version__",
    "Agent",
    "AgentManager",
    "get_agent_manager",
    "AgentAwareMemoryStore",
    "AgentAwareSkillRegistry",
]