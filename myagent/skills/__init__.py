"""Skill system for MyAgent."""

from myagent.skills.base import Skill, SkillInfo, parse_skill_md
from myagent.skills.registry import SkillRegistry, get_skill_registry, tool
from myagent.skills.agent_registry import AgentAwareSkillRegistry

__all__ = [
    "Skill",
    "SkillInfo",
    "parse_skill_md",
    "SkillRegistry",
    "AgentAwareSkillRegistry",
    "get_skill_registry",
    "tool",
]