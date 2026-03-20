"""Skill registry and discovery."""

import importlib.util
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from myagent.config import get_settings
from myagent.skills.base import Skill, SkillInfo, parse_skill_md


# Global registry instance
_skill_registry_instance: Optional['SkillRegistry'] = None


def get_skill_registry() -> 'SkillRegistry':
    """Get or create global skill registry."""
    global _skill_registry_instance
    if _skill_registry_instance is None:
        _skill_registry_instance = SkillRegistry()
    return _skill_registry_instance


class SkillRegistry:
    """Registry for managing skills."""
    
    # Class-level flag to track if watcher is already set up
    _watcher_initialized: bool = False
    
    def __init__(self):
        self.settings = get_settings()
        self._skills: Dict[str, Skill] = {}
        self._observer: Optional[Observer] = None
        self.discover_skills()
        
        if self.settings.auto_reload_skills and not SkillRegistry._watcher_initialized:
            self._setup_watcher()
            SkillRegistry._watcher_initialized = True
    
    def discover_skills(self):
        """Discover all skills in the skills directory."""
        skills_dir = self.settings.skills_dir
        if not skills_dir.exists():
            return
        
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                self._load_skill(skill_dir)
    
    def _load_skill(self, skill_dir: Path) -> Optional[Skill]:
        """Load a skill from directory."""
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            return None
        
        try:
            content = skill_md.read_text(encoding="utf-8")
            info = parse_skill_md(content, skill_dir)
            
            if info is None:
                return None
            
            skill = Skill(info)
            
            # Load tools.py if exists
            tools_py = skill_dir / "tools.py"
            if tools_py.exists():
                self._load_tools(skill, tools_py)
            
            self._skills[info.name] = skill
            return skill
            
        except Exception as e:
            print(f"Failed to load skill from {skill_dir}: {e}")
            return None
    
    def _load_tools(self, skill: Skill, tools_py: Path):
        """Load tools from a Python file."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"skill_{skill.info.name}", tools_py
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            
            # Find tool functions
            if hasattr(module, "register_tools"):
                module.register_tools(skill)
            else:
                # Auto-discover functions with @tool decorator
                for name in dir(module):
                    obj = getattr(module, name)
                    if callable(obj) and hasattr(obj, "_is_tool"):
                        skill.register_tool(getattr(obj, "_tool_name", name), obj)
                        
        except Exception as e:
            print(f"Failed to load tools from {tools_py}: {e}")
    
    def _setup_watcher(self):
        """Setup file watcher for auto-reload."""
        # Check if observer already exists and is running
        if self._observer is not None:
            return
        
        # Check if skills_dir exists before setting up watcher
        if not self.settings.skills_dir.exists():
            return
        
        class SkillHandler(FileSystemEventHandler):
            def __init__(self, registry):
                self.registry = registry
            
            def on_modified(self, event):
                if event.src_path.endswith("SKILL.md") or event.src_path.endswith("tools.py"):
                    self.registry.discover_skills()
        
        self._observer = Observer()
        self._observer.schedule(
            SkillHandler(self),
            str(self.settings.skills_dir),
            recursive=True
        )
        self._observer.start()
    
    def get(self, name: str) -> Optional[Skill]:
        """Get a skill by name."""
        return self._skills.get(name)
    
    def list_all(self) -> List[SkillInfo]:
        """List all registered skills."""
        return [skill.info for skill in self._skills.values()]
    
    def find_by_tag(self, tag: str) -> List[SkillInfo]:
        """Find skills by tag."""
        return [
            skill.info for skill in self._skills.values()
            if tag in skill.info.tags
        ]
    
    def get_all_tools(self) -> Dict[str, Callable]:
        """Get all tools from all skills."""
        tools = {}
        for skill in self._skills.values():
            for tool_name in skill.list_tools():
                tools[f"{skill.info.name}.{tool_name}"] = skill.get_tool(tool_name)
        return tools
    
    def reload(self):
        """Reload all skills."""
        self._skills.clear()
        self.discover_skills()
    
    def stop_watcher(self):
        """Stop the file watcher."""
        if self._observer:
            self._observer.stop()
            self._observer.join()


def tool(name: Optional[str] = None):
    """Decorator to mark a function as a tool."""
    def decorator(func):
        func._is_tool = True
        func._tool_name = name or func.__name__
        return func
    return decorator
