"""Agent-aware skill registry supporting shared and agent-private skills."""

import os
from typing import Callable, Dict, List, Optional
from pathlib import Path

from myagent.agent.manager import AgentManager, get_agent_manager
from myagent.agent.models import Agent
from myagent.skills.base import Skill, SkillInfo
from myagent.skills.registry import SkillRegistry


class AgentAwareSkillRegistry:
    """Skill registry that combines project-level, agent-private, and shared skills.
    
    Skill Priority (highest to lowest):
    1. Project-level skills: ./.agents/skills/ (current working directory)
    2. Agent-private skills: ~/Library/.../agents/agent-{id}/skills/
    3. Master shared skills: ~/Library/.../shared_skills/
    """
    
    PROJECT_SKILLS_DIR = ".agents/skills"
    
    def __init__(self, agent: Optional[Agent] = None, 
                 agent_manager: Optional[AgentManager] = None):
        self.agent_manager = agent_manager or get_agent_manager()
        self.agent = agent or self.agent_manager.get_current_agent()
        
        # Initialize shared registry (always loaded)
        from myagent.config import get_settings
        shared_skills_dir = get_settings().config_dir / "shared_skills"
        self.shared_registry = SkillRegistry(skills_dir=shared_skills_dir)
        
        # Initialize agent-private registry (if agent has private skills)
        self.private_registry: Optional[SkillRegistry] = None
        if self.agent.skills_dir and self.agent.skills_dir.exists():
            self.private_registry = SkillRegistry(skills_dir=self.agent.skills_dir)
        
        # Initialize project-level registry (if exists in current working directory)
        self.project_registry: Optional[SkillRegistry] = None
        self._init_project_registry()
    
    def _init_project_registry(self):
        """Initialize project-level skill registry from current working directory."""
        cwd = Path(os.getcwd())
        project_skills = cwd / self.PROJECT_SKILLS_DIR
        
        if project_skills.exists() and project_skills.is_dir():
            self.project_registry = SkillRegistry(skills_dir=project_skills)
            # Sync project skills to agent's private storage for persistence
            self._sync_project_to_agent(project_skills)
    
    def _sync_project_to_agent(self, project_skills_dir: Path):
        """Sync project-level skills to agent's private storage."""
        if not self.agent.skills_dir:
            return
        
        import shutil
        self.agent.skills_dir.mkdir(parents=True, exist_ok=True)
        
        for skill_dir in project_skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            target = self.agent.skills_dir / skill_dir.name
            if target.exists():
                # Skip if already exists (don't overwrite)
                continue
            
            try:
                shutil.copytree(skill_dir, target)
            except Exception as e:
                print(f"Warning: Failed to sync skill {skill_dir.name}: {e}")
    
    def list_all(self) -> List[SkillInfo]:
        """List all available skills based on inheritance settings.
        
        Priority: Project > Agent-Private > Shared
        """
        skills = []
        skill_names = set()
        
        # Priority 1: Project-level skills (highest priority)
        if self.project_registry:
            for skill in self.project_registry.list_all():
                skills.append(skill)
                skill_names.add(skill.name)
        
        # Priority 2: Agent-private skills
        if self.private_registry:
            for skill in self.private_registry.list_all():
                if skill.name not in skill_names:
                    skills.append(skill)
                    skill_names.add(skill.name)
        
        # Priority 3: Master shared skills (lowest priority)
        if self.agent.inherit_shared_skills:
            for skill in self.shared_registry.list_all():
                if skill.name not in skill_names:
                    skills.append(skill)
                    skill_names.add(skill.name)
        
        return skills
    
    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name.
        
        Priority: Project > Agent-Private > Shared
        """
        # Priority 1: Project-level skills
        if self.project_registry:
            skill = self.project_registry.get(name)
            if skill:
                return skill
        
        # Priority 2: Agent-private skills
        if self.private_registry:
            skill = self.private_registry.get(name)
            if skill:
                return skill
        
        # Priority 3: Master shared skills
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
        """Get all available tools.
        
        Priority: Project > Agent-Private > Shared
        """
        tools = {}
        skill_names = set()
        
        # Priority 1: Project-level tools
        if self.project_registry:
            for skill_name, tool_dict in self.project_registry.get_all_tools().items():
                tools[f"{skill_name} (project)"] = tool_dict
                skill_names.add(skill_name)
        
        # Priority 2: Agent-private tools
        if self.private_registry:
            for skill_name, tool_dict in self.private_registry.get_all_tools().items():
                if skill_name not in skill_names:
                    tools[f"{skill_name} (private)"] = tool_dict
                    skill_names.add(skill_name)
        
        # Priority 3: Master shared tools
        if self.agent.inherit_shared_skills:
            for skill_name, tool_dict in self.shared_registry.get_all_tools().items():
                if skill_name not in skill_names:
                    tools[skill_name] = tool_dict
                    skill_names.add(skill_name)
        
        return tools
    
    def list_tools_flat(self) -> List[tuple]:
        """List all tools as (skill_name, tool_name, callable, origin) tuples.
        
        Origin: 'project' | 'private' | 'shared'
        """
        tools = []
        skill_tool_pairs = set()
        
        # Priority 1: Project-level tools
        if self.project_registry:
            for skill_name, tool_name, func in self.project_registry.list_tools_flat():
                tools.append((skill_name, tool_name, func, 'project'))
                skill_tool_pairs.add((skill_name, tool_name))
        
        # Priority 2: Agent-private tools
        if self.private_registry:
            for skill_name, tool_name, func in self.private_registry.list_tools_flat():
                if (skill_name, tool_name) not in skill_tool_pairs:
                    tools.append((skill_name, tool_name, func, 'private'))
                    skill_tool_pairs.add((skill_name, tool_name))
        
        # Priority 3: Master shared tools
        if self.agent.inherit_shared_skills:
            for skill_name, tool_name, func in self.shared_registry.list_tools_flat():
                if (skill_name, tool_name) not in skill_tool_pairs:
                    tools.append((skill_name, tool_name, func, 'shared'))
                    skill_tool_pairs.add((skill_name, tool_name))
        
        return tools
    
    def find_by_tag(self, tag: str) -> List[SkillInfo]:
        """Find skills by tag.
        
        Priority: Project > Agent-Private > Shared
        """
        results = []
        existing_names = set()
        
        # Priority 1: Project-level skills
        if self.project_registry:
            for skill in self.project_registry.find_by_tag(tag):
                results.append(skill)
                existing_names.add(skill.name)
        
        # Priority 2: Agent-private skills
        if self.private_registry:
            for skill in self.private_registry.find_by_tag(tag):
                if skill.name not in existing_names:
                    results.append(skill)
                    existing_names.add(skill.name)
        
        # Priority 3: Master shared skills
        if self.agent.inherit_shared_skills:
            for skill in self.shared_registry.find_by_tag(tag):
                if skill.name not in existing_names:
                    results.append(skill)
                    existing_names.add(skill.name)
        
        return results
    
    def reload(self):
        """Reload all skills."""
        # Re-check project registry (in case cwd changed)
        self._init_project_registry()
        
        if self.project_registry:
            self.project_registry.reload()
        if self.private_registry:
            self.private_registry.reload()
        self.shared_registry.reload()
    
    def get_shared_registry(self) -> SkillRegistry:
        """Get the shared skill registry."""
        return self.shared_registry
    
    def get_private_registry(self) -> Optional[SkillRegistry]:
        """Get the private skill registry."""
        return self.private_registry
    
    def get_project_registry(self) -> Optional[SkillRegistry]:
        """Get the project-level skill registry."""
        return self.project_registry
    
    def has_private_skills(self) -> bool:
        """Check if agent has any private skills (excluding project-level)."""
        if not self.private_registry:
            return False
        return len(self.private_registry.list_all()) > 0
    
    def has_project_skills(self) -> bool:
        """Check if current project has any skills."""
        if not self.project_registry:
            return False
        return len(self.project_registry.list_all()) > 0
    
    def get_skill_origin(self, skill_name: str) -> Optional[str]:
        """Get the origin of a skill: 'project', 'private', 'shared', or None."""
        if self.project_registry and self.project_registry.get(skill_name):
            return 'project'
        if self.private_registry and self.private_registry.get(skill_name):
            return 'private'
        if self.shared_registry.get(skill_name):
            return 'shared'
        return None