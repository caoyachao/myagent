"""Agent-aware skill registry supporting shared and private skills."""

from typing import Callable, Dict, List, Optional
from pathlib import Path

from myagent.agent.manager import AgentManager, get_agent_manager
from myagent.agent.models import Agent
from myagent.skills.base import Skill, SkillInfo
from myagent.skills.registry import SkillRegistry


class AgentAwareSkillRegistry:
    """Skill registry that combines shared and agent-private skills."""
    
    def __init__(self, agent: Optional[Agent] = None, 
                 agent_manager: Optional[AgentManager] = None):
        self.agent_manager = agent_manager or get_agent_manager()
        self.agent = agent or self.agent_manager.get_current_agent()
        
        # Initialize shared registry (always loaded)
        from myagent.config import get_settings
        shared_skills_dir = get_settings().config_dir / "shared_skills"
        self.shared_registry = SkillRegistry(skills_dir=shared_skills_dir)
        
        # Initialize private registry (if agent has private skills)
        self.private_registry: Optional[SkillRegistry] = None
        if self.agent.skills_dir and self.agent.skills_dir.exists():
            self.private_registry = SkillRegistry(skills_dir=self.agent.skills_dir)
    
    def list_all(self) -> List[SkillInfo]:
        """List all available skills based on inheritance settings."""
        skills = []
        
        # Add private skills first (they take precedence)
        if self.private_registry:
            skills.extend(self.private_registry.list_all())
        
        # Add shared skills if inheritance is enabled
        if self.agent.inherit_shared_skills:
            shared_skills = self.shared_registry.list_all()
            # Filter out duplicates (private skills with same name take precedence)
            private_names = {s.name for s in skills}
            for skill in shared_skills:
                if skill.name not in private_names:
                    skills.append(skill)
        
        return skills
    
    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        # Check private skills first
        if self.private_registry:
            skill = self.private_registry.get(name)
            if skill:
                return skill
        
        # Fall back to shared skills if inheritance is enabled
        if self.agent.inherit_shared_skills:
            return self.shared_registry.get(name)
        
        return None
    
    def get_skill_info(self, name: str) -> Optional[SkillInfo]:
        """Get skill info by name."""
        skill = self.get(name)
        return skill.info if skill else None
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name (supports 'skill_name.tool_name' format)."""
        if "." in name:
            # Format: skill_name.tool_name
            skill_name, tool_name = name.split(".", 1)
            skill = self.get(skill_name)
            if skill:
                return skill.get_tool(tool_name)
        else:
            # Try to find tool in any skill
            for skill_info in self.list_all():
                skill = self.get(skill_info.name)
                if skill:
                    tool = skill.get_tool(name)
                    if tool:
                        return tool
        
        return None
    
    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all available tools."""
        tools = {}
        
        # Add private tools first
        if self.private_registry:
            for skill_name, tool_dict in self.private_registry.get_all_tools().items():
                tools[f"{skill_name} (private)"] = tool_dict
        
        # Add shared tools if inheritance is enabled
        if self.agent.inherit_shared_skills:
            for skill_name, tool_dict in self.shared_registry.get_all_tools().items():
                if skill_name not in tools:
                    tools[skill_name] = tool_dict
        
        return tools
    
    def list_tools_flat(self) -> List[tuple]:
        """List all tools as (skill_name, tool_name, callable) tuples."""
        tools = []
        
        # Private tools
        if self.private_registry:
            for skill_name, tool_name, func in self.private_registry.list_tools_flat():
                tools.append((skill_name, tool_name, func, True))  # True = is_private
        
        # Shared tools
        if self.agent.inherit_shared_skills:
            for skill_name, tool_name, func in self.shared_registry.list_tools_flat():
                # Check if not overridden by private
                if not any(t[0] == skill_name and t[1] == tool_name for t in tools):
                    tools.append((skill_name, tool_name, func, False))  # False = is_shared
        
        return tools
    
    def find_by_tag(self, tag: str) -> List[SkillInfo]:
        """Find skills by tag."""
        results = []
        
        if self.private_registry:
            results.extend(self.private_registry.find_by_tag(tag))
        
        if self.agent.inherit_shared_skills:
            shared = self.shared_registry.find_by_tag(tag)
            existing_names = {s.name for s in results}
            for skill in shared:
                if skill.name not in existing_names:
                    results.append(skill)
        
        return results
    
    def reload(self):
        """Reload all skills."""
        self.shared_registry.reload()
        if self.private_registry:
            self.private_registry.reload()
    
    def get_shared_registry(self) -> SkillRegistry:
        """Get the shared skill registry."""
        return self.shared_registry
    
    def get_private_registry(self) -> Optional[SkillRegistry]:
        """Get the private skill registry."""
        return self.private_registry
    
    def has_private_skills(self) -> bool:
        """Check if agent has any private skills."""
        if not self.private_registry:
            return False
        return len(self.private_registry.list_all()) > 0