"""Agent data cleaner for complete deletion."""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from myagent.agent.manager import AgentManager
    from myagent.agent.models import Agent


@dataclass
class CleanupStats:
    """Statistics about cleanup operation."""
    memory_deleted: bool = False
    memory_size_mb: float = 0.0
    chroma_deleted: bool = False
    chroma_files_deleted: int = 0
    skills_deleted: int = 0
    config_deleted: bool = False
    cache_deleted: bool = False
    errors: list = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class AgentCleaner:
    """Cleans up all data associated with an agent."""
    
    def __init__(self, agent_manager: "AgentManager"):
        self.agent_manager = agent_manager
    
    def cleanup_agent_data(self, agent: "Agent") -> CleanupStats:
        """
        Completely remove all data associated with an agent.
        
        This includes:
        - Memory database (SQLite)
        - Vector embeddings (ChromaDB)
        - Private skills
        - Configuration files
        - Cache files
        """
        stats = CleanupStats()
        
        # 1. Close any open connections
        self._close_connections(agent)
        
        # 2. Delete memory database
        if agent.memory_db_path and agent.memory_db_path.exists():
            try:
                size = agent.memory_db_path.stat().st_size / (1024 * 1024)
                agent.memory_db_path.unlink()
                stats.memory_deleted = True
                stats.memory_size_mb = round(size, 2)
            except Exception as e:
                stats.errors.append(f"Failed to delete memory DB: {e}")
        
        # 3. Delete Chroma vector store
        if agent.chroma_path and agent.chroma_path.exists():
            try:
                file_count = len(list(agent.chroma_path.rglob("*")))
                shutil.rmtree(agent.chroma_path)
                stats.chroma_deleted = True
                stats.chroma_files_deleted = file_count
            except Exception as e:
                stats.errors.append(f"Failed to delete Chroma: {e}")
        
        # 4. Delete private skills
        if agent.skills_dir and agent.skills_dir.exists() and not agent.is_master:
            try:
                skill_count = len([d for d in agent.skills_dir.iterdir() if d.is_dir()])
                shutil.rmtree(agent.skills_dir)
                stats.skills_deleted = skill_count
            except Exception as e:
                stats.errors.append(f"Failed to delete skills: {e}")
        
        # 5. Delete configuration
        if agent.config_path and agent.config_path.exists():
            try:
                agent.config_path.unlink()
                stats.config_deleted = True
                
                # Try to remove parent directory if empty
                try:
                    if agent.config_path.parent.exists():
                        agent.config_path.parent.rmdir()
                except OSError:
                    pass  # Directory not empty
                    
            except Exception as e:
                stats.errors.append(f"Failed to delete config: {e}")
        
        # 6. Delete cache
        cache_dir = self._get_cache_dir(agent.id)
        if cache_dir and cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                stats.cache_deleted = True
            except Exception as e:
                stats.errors.append(f"Failed to delete cache: {e}")
        
        # 7. Clean up empty agent data directory
        self._cleanup_empty_dirs(agent)
        
        return stats
    
    def _close_connections(self, agent: "Agent"):
        """Close any open database connections for the agent."""
        # In a real implementation, we might need to track open connections
        # For now, this is a placeholder
        pass
    
    def _get_cache_dir(self, agent_id: str) -> Path:
        """Get cache directory for an agent."""
        from myagent.config import get_settings
        cache_base = get_settings().data_dir / "cache"
        return cache_base / f"agent-{agent_id}"
    
    def _cleanup_empty_dirs(self, agent: "Agent"):
        """Clean up empty directories after deletion."""
        # Check agent data directory
        if not agent.is_master:
            agent_data_dir = agent.memory_db_path.parent if agent.memory_db_path else None
            if agent_data_dir and agent_data_dir.exists():
                try:
                    # Only remove if empty
                    if not any(agent_data_dir.iterdir()):
                        agent_data_dir.rmdir()
                except OSError:
                    pass
            
            # Check agent config directory
            agent_config_dir = agent.config_path.parent if agent.config_path else None
            if agent_config_dir and agent_config_dir.exists():
                try:
                    if not any(agent_config_dir.iterdir()):
                        agent_config_dir.rmdir()
                except OSError:
                    pass
    
    def verify_cleanup(self, agent_id: str) -> dict:
        """Verify that all data for an agent has been cleaned up."""
        agent = self.agent_manager.get_agent(agent_id)
        
        checks = []
        all_clean = True
        
        if agent:
            paths_to_check = [
                ("Memory DB", agent.memory_db_path),
                ("Chroma", agent.chroma_path),
                ("Skills", agent.skills_dir),
                ("Config", agent.config_path),
                ("Cache", self._get_cache_dir(agent_id)),
            ]
            
            for name, path in paths_to_check:
                if path:
                    exists = path.exists()
                    checks.append({
                        "name": name,
                        "path": str(path),
                        "exists": exists,
                        "status": "❌ 存在" if exists else "✓ 已清理"
                    })
                    if exists:
                        all_clean = False
        
        return {
            "agent_id": agent_id,
            "all_clean": all_clean,
            "checks": checks
        }
    
    def cleanup_orphaned_data(self) -> list:
        """
        Find and clean up orphaned data (data without corresponding agent config).
        
        Returns list of cleaned up items.
        """
        cleaned = []
        
        from myagent.config import get_settings
        settings = get_settings()
        
        # Check agents data directory
        agents_data_dir = settings.data_dir / "agents"
        if agents_data_dir.exists():
            for agent_dir in agents_data_dir.iterdir():
                if not agent_dir.is_dir():
                    continue
                
                # Extract agent ID from directory name
                if agent_dir.name.startswith("agent-"):
                    agent_id = agent_dir.name.replace("agent-", "")
                    
                    # Check if agent exists in registry
                    if not self.agent_manager.get_agent(agent_id):
                        # Orphaned data - clean it up
                        try:
                            shutil.rmtree(agent_dir)
                            cleaned.append({
                                "type": "data_directory",
                                "agent_id": agent_id,
                                "path": str(agent_dir)
                            })
                        except Exception as e:
                            cleaned.append({
                                "type": "data_directory",
                                "agent_id": agent_id,
                                "path": str(agent_dir),
                                "error": str(e)
                            })
        
        # Check agents config directory
        agents_config_dir = settings.config_dir / "agents"
        if agents_config_dir.exists():
            for agent_dir in agents_config_dir.iterdir():
                if not agent_dir.is_dir():
                    continue
                
                if agent_dir.name.startswith("agent-"):
                    agent_id = agent_dir.name.replace("agent-", "")
                    
                    if not self.agent_manager.get_agent(agent_id):
                        try:
                            shutil.rmtree(agent_dir)
                            cleaned.append({
                                "type": "config_directory",
                                "agent_id": agent_id,
                                "path": str(agent_dir)
                            })
                        except Exception as e:
                            cleaned.append({
                                "type": "config_directory",
                                "agent_id": agent_id,
                                "path": str(agent_dir),
                                "error": str(e)
                            })
        
        return cleaned