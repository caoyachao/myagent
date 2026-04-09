"""Skill management tools for installing, uninstalling, and managing skills."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

from myagent.config import get_settings
from myagent.agent.manager import AgentManager, get_agent_manager


class SkillManager:
    """Manager for installing and managing skills from various sources."""
    
    CLAWHUB_REGISTRY_URL = "https://clawhub.ai"
    
    def __init__(self, agent_manager: Optional[AgentManager] = None):
        self.agent_manager = agent_manager or get_agent_manager()
        self.settings = get_settings()
    
    def install_from_clawhub(self, slug: str, scope: str = "shared", 
                             version: Optional[str] = None) -> Dict[str, Any]:
        """Install a skill from ClawHub.
        
        Args:
            slug: Skill slug (e.g., 'caoyachao/think-plan' or 'think-plan')
            scope: 'shared' for all agents, 'private' for current agent only
            version: Specific version to install (default: latest)
            
        Returns:
            Dict with installation result
        """
        # Determine target directory based on scope
        if scope == "shared":
            target_dir = self.settings.config_dir / "shared_skills"
        elif scope == "private":
            current_agent = self.agent_manager.get_current_agent()
            if not current_agent.skills_dir:
                return {
                    "success": False,
                    "error": f"Current agent {current_agent.name} does not have a skills directory"
                }
            target_dir = current_agent.skills_dir
        else:
            return {
                "success": False,
                "error": f"Invalid scope '{scope}'. Must be 'shared' or 'private'"
            }
        
        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if already installed
        skill_name = slug.split("/")[-1] if "/" in slug else slug
        existing_path = target_dir / skill_name
        if existing_path.exists():
            return {
                "success": False,
                "error": f"Skill '{skill_name}' is already installed at {existing_path}",
                "suggestion": "Use uninstall_skill first, or use reinstall=True"
            }
        
        # Execute clawhub install
        cmd = ["clawhub", "install", slug]
        if version:
            cmd.extend(["--version", version])
        
        try:
            # Run clawhub install in target directory
            result = subprocess.run(
                cmd,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"ClawHub install failed: {result.stderr}",
                    "stdout": result.stdout
                }
            
            # Verify installation
            installed_path = target_dir / skill_name
            if not installed_path.exists():
                return {
                    "success": False,
                    "error": "Installation reported success but skill directory not found"
                }
            
            # Read SKILL.md for metadata
            skill_info = self._read_skill_metadata(installed_path)
            
            return {
                "success": True,
                "skill_name": skill_name,
                "slug": slug,
                "version": skill_info.get("version", "unknown"),
                "scope": scope,
                "install_path": str(installed_path),
                "description": skill_info.get("description", ""),
                "message": f"Successfully installed '{skill_name}' ({scope})"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Installation timed out after 120 seconds"
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "clawhub command not found. Please install with: npm install -g clawhub"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error during installation: {str(e)}"
            }
    
    def uninstall(self, skill_name: str, scope: Optional[str] = None) -> Dict[str, Any]:
        """Uninstall a skill.
        
        Args:
            skill_name: Name of the skill to uninstall
            scope: 'shared', 'private', or None (will search both)
            
        Returns:
            Dict with uninstallation result
        """
        # Determine where to look
        locations_to_check = []
        
        if scope in (None, "shared"):
            shared_dir = self.settings.config_dir / "shared_skills"
            locations_to_check.append(("shared", shared_dir))
        
        if scope in (None, "private"):
            current_agent = self.agent_manager.get_current_agent()
            if current_agent.skills_dir:
                locations_to_check.append(("private", current_agent.skills_dir))
        
        # Search for skill
        found_locations = []
        for loc_scope, loc_dir in locations_to_check:
            skill_path = loc_dir / skill_name
            if skill_path.exists():
                found_locations.append((loc_scope, skill_path))
        
        if not found_locations:
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found in specified scope(s)"
            }
        
        if len(found_locations) > 1 and scope is None:
            # Skill found in multiple locations, ask for clarification
            scopes_found = ", ".join([loc[0] for loc in found_locations])
            return {
                "success": False,
                "error": f"Skill '{skill_name}' found in multiple scopes: {scopes_found}",
                "suggestion": f"Please specify scope: 'shared' or 'private'"
            }
        
        # Uninstall from the found location
        loc_scope, skill_path = found_locations[0]
        
        try:
            shutil.rmtree(skill_path)
            return {
                "success": True,
                "skill_name": skill_name,
                "scope": loc_scope,
                "removed_path": str(skill_path),
                "message": f"Successfully uninstalled '{skill_name}' from {loc_scope}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to remove skill directory: {str(e)}"
            }
    
    def search_clawhub(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for skills on ClawHub.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            Dict with search results
        """
        try:
            result = subprocess.run(
                ["clawhub", "search", query, "--limit", str(limit)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Search failed: {result.stderr}"
                }
            
            # Parse results (clawhub search output format may vary)
            return {
                "success": True,
                "query": query,
                "results": result.stdout,
                "count": len([l for l in result.stdout.split('\n') if l.strip()])
            }
            
        except FileNotFoundError:
            return {
                "success": False,
                "error": "clawhub command not found. Please install with: npm install -g clawhub"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Search error: {str(e)}"
            }
    
    def list_installed(self, scope: Optional[str] = None) -> Dict[str, Any]:
        """List installed skills.
        
        Args:
            scope: 'shared', 'private', 'all', or None (all)
            
        Returns:
            Dict with list of installed skills
        """
        result = {
            "shared": [],
            "private": [],
            "current_agent": self.agent_manager.get_current_agent().name
        }
        
        # Get shared skills
        if scope in (None, "all", "shared"):
            shared_dir = self.settings.config_dir / "shared_skills"
            if shared_dir.exists():
                for skill_dir in shared_dir.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        meta = self._read_skill_metadata(skill_dir)
                        result["shared"].append({
                            "name": skill_dir.name,
                            "path": str(skill_dir),
                            **meta
                        })
        
        # Get private skills for current agent
        if scope in (None, "all", "private"):
            current_agent = self.agent_manager.get_current_agent()
            if current_agent.skills_dir and current_agent.skills_dir.exists():
                for skill_dir in current_agent.skills_dir.iterdir():
                    if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                        meta = self._read_skill_metadata(skill_dir)
                        result["private"].append({
                            "name": skill_dir.name,
                            "path": str(skill_dir),
                            **meta
                        })
        
        return result
    
    def get_skill_info(self, skill_name: str) -> Dict[str, Any]:
        """Get detailed information about an installed skill.
        
        Args:
            skill_name: Name of the skill
            
        Returns:
            Dict with skill information
        """
        # Search in all locations
        locations = [
            ("shared", self.settings.config_dir / "shared_skills" / skill_name),
        ]
        
        current_agent = self.agent_manager.get_current_agent()
        if current_agent.skills_dir:
            locations.append(("private", current_agent.skills_dir / skill_name))
        
        for scope, skill_path in locations:
            if skill_path.exists() and (skill_path / "SKILL.md").exists():
                meta = self._read_skill_metadata(skill_path)
                return {
                    "found": True,
                    "name": skill_name,
                    "scope": scope,
                    "path": str(skill_path),
                    **meta
                }
        
        return {
            "found": False,
            "name": skill_name,
            "error": f"Skill '{skill_name}' not found"
        }
    
    def update_skill(self, skill_name: str) -> Dict[str, Any]:
        """Update a skill to the latest version.
        
        Args:
            skill_name: Name of the skill to update
            
        Returns:
            Dict with update result
        """
        # First find where it's installed
        info = self.get_skill_info(skill_name)
        if not info.get("found"):
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found"
            }
        
        scope = info["scope"]
        
        # For now, we uninstall and reinstall
        # In the future, this could be more sophisticated with version checking
        uninstall_result = self.uninstall(skill_name, scope=scope)
        if not uninstall_result.get("success"):
            return uninstall_result
        
        # Reinstall - we need to determine the original slug
        # This could be stored in metadata in the future
        slug = skill_name  # Fallback to skill name
        
        return self.install_from_clawhub(slug, scope=scope)
    
    def _read_skill_metadata(self, skill_path: Path) -> Dict[str, Any]:
        """Read metadata from SKILL.md file."""
        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            return {"description": "", "version": "unknown", "author": ""}
        
        try:
            content = skill_md.read_text(encoding="utf-8")
            
            # Parse YAML frontmatter
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    frontmatter = parts[1].strip()
                    body = parts[2].strip()
                    
                    # Simple YAML-like parsing
                    meta = {"description": "", "version": "", "author": "", "tags": []}
                    for line in frontmatter.split("\n"):
                        if ":" in line and not line.strip().startswith("-"):
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            if key in meta:
                                meta[key] = value
                    
                    meta["full_description"] = body[:200] + "..." if len(body) > 200 else body
                    return meta
            
            return {"description": content[:100] + "...", "version": "", "author": ""}
            
        except Exception:
            return {"description": "", "version": "unknown", "author": ""}


# Singleton instance
_skill_manager_instance: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    """Get or create global skill manager instance."""
    global _skill_manager_instance
    if _skill_manager_instance is None:
        _skill_manager_instance = SkillManager()
    return _skill_manager_instance
