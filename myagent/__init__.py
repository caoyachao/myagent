"""MyAgent - A local memory-enhanced agent layer for Kimi Code CLI."""

__version__ = "0.1.0"

from myagent.config import Settings, get_settings
from myagent.memory.store import MemoryStore, Memory
from myagent.skills.base import Skill, SkillInfo
from myagent.skills.registry import SkillRegistry, tool
from myagent.tools.registry import ToolRegistry, register_tool

__all__ = [
    "Settings",
    "get_settings",
    "MemoryStore",
    "Memory",
    "Skill",
    "SkillInfo",
    "SkillRegistry",
    "tool",
    "ToolRegistry",
    "register_tool",
]
