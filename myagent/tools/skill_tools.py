"""Built-in skill management tools."""

from typing import Optional

from myagent.skills.registry import SkillRegistry, get_settings
from myagent.tools.registry import register_tool


# Global skill registry instance
_skill_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """Get or create global skill registry."""
    global _skill_registry
    if _skill_registry is None:
        _skill_registry = SkillRegistry()
    return _skill_registry


@register_tool(
    name="list_skills",
    description="List all available skills"
)
def list_skills() -> str:
    """List all registered skills."""
    registry = get_skill_registry()
    skills = registry.list_all()
    
    if not skills:
        return "No skills registered."
    
    lines = [f"Available skills ({len(skills)} total):"]
    for skill in skills:
        lines.append(f"\n• {skill.name}")
        lines.append(f"  {skill.description}")
        if skill.tools:
            lines.append(f"  Tools: {', '.join(skill.tools)}")
        if skill.tags:
            lines.append(f"  Tags: {', '.join(skill.tags)}")
    
    return "\n".join(lines)


@register_tool(
    name="get_skill_info",
    description="Get detailed information about a specific skill"
)
def get_skill_info(skill_name: str) -> str:
    """
    Get detailed information about a skill.
    
    Args:
        skill_name: The name of the skill
    """
    registry = get_skill_registry()
    skill = registry.get(skill_name)
    
    if skill is None:
        return f"Skill '{skill_name}' not found."
    
    info = skill.info
    lines = [
        f"Skill: {info.name}",
        f"Version: {info.version}",
        f"Description: {info.description}",
    ]
    
    if info.author:
        lines.append(f"Author: {info.author}")
    if info.tools:
        lines.append(f"Tools: {', '.join(info.tools)}")
    if info.tags:
        lines.append(f"Tags: {', '.join(info.tags)}")
    
    lines.append(f"\n{info.content}")
    
    return "\n".join(lines)


@register_tool(
    name="reload_skills",
    description="Reload all skills from disk"
)
def reload_skills() -> str:
    """Reload all skills from disk."""
    registry = get_skill_registry()
    registry.reload()
    return "Skills reloaded successfully."


@register_tool(
    name="get_skills_directory",
    description="Get the path to the skills directory"
)
def get_skills_directory() -> str:
    """Get the path where skills are stored."""
    settings = get_settings()
    return f"Skills are stored in: {settings.skills_dir}\n\nTo add a new skill:\n1. Create a directory under this path\n2. Add a SKILL.md file with YAML frontmatter\n3. Optionally add a tools.py file"
