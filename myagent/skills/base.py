"""Base classes and types for skills."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
import yaml


@dataclass
class SkillInfo:
    """Information about a skill."""
    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    path: Optional[Path] = None
    content: str = ""
    
    def to_prompt_section(self) -> str:
        """Format skill info for system prompt."""
        lines = [
            f"## {self.name}",
            f"{self.description}",
        ]
        if self.tools:
            lines.append(f"**可用工具**: {', '.join(self.tools)}")
        lines.append("")
        return "\n".join(lines)


class Skill:
    """A skill that can be loaded and executed."""
    
    def __init__(self, info: SkillInfo):
        self.info = info
        self._tools: Dict[str, Callable] = {}
    
    def register_tool(self, name: str, func: Callable):
        """Register a tool for this skill."""
        self._tools[name] = func
        if name not in self.info.tools:
            self.info.tools.append(name)
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[str]:
        """List all available tools."""
        return list(self._tools.keys())
    
    def get_system_prompt_addition(self) -> str:
        """Get additional system prompt content for this skill."""
        return self.info.content


def parse_skill_md(content: str, path: Optional[Path] = None) -> Optional[SkillInfo]:
    """Parse a SKILL.md file with YAML frontmatter."""
    # Split frontmatter and content
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if not match:
        return None
    
    try:
        frontmatter = yaml.safe_load(match.group(1))
        body = match.group(2).strip()
        
        return SkillInfo(
            name=frontmatter.get("name", path.stem if path else "unknown"),
            description=frontmatter.get("description", ""),
            version=frontmatter.get("version", "1.0.0"),
            author=frontmatter.get("author", ""),
            tags=frontmatter.get("tags", []),
            tools=frontmatter.get("tools", []),
            path=path,
            content=body
        )
    except Exception:
        return None
