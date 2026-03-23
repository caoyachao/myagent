"""Agent data models for MyAgent 2.0."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from myagent.config import get_settings


@dataclass
class Agent:
    """An agent with its own memory, skills and personality."""
    
    # Basic info
    id: str
    name: str
    description: str = ""
    
    # Personality
    personality: str = ""
    system_prompt: str = ""
    
    # Inheritance settings
    inherit_shared_skills: bool = True
    inherit_shared_tools: bool = True
    inherit_master_memories: bool = False
    
    # Storage paths (relative to base dirs)
    memory_db_path: Optional[Path] = None
    chroma_path: Optional[Path] = None
    skills_dir: Optional[Path] = None
    config_path: Optional[Path] = None
    
    # Metadata
    is_master: bool = False
    is_active: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Migration info
    migrated_from_v1: bool = False
    migrated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """Initialize derived paths if not set."""
        settings = get_settings()
        
        if self.is_master:
            # Master agent uses fixed paths
            if self.memory_db_path is None:
                self.memory_db_path = settings.data_dir / "master" / "memories.db"
            if self.chroma_path is None:
                self.chroma_path = settings.data_dir / "master" / "chroma"
            if self.skills_dir is None:
                self.skills_dir = settings.config_dir / "shared_skills"
            if self.config_path is None:
                self.config_path = settings.config_dir / "master" / "agent.json"
        else:
            # Regular agents use agent-specific paths
            agent_base = f"agent-{self.id}"
            if self.memory_db_path is None:
                self.memory_db_path = settings.data_dir / "agents" / agent_base / "memories.db"
            if self.chroma_path is None:
                self.chroma_path = settings.data_dir / "agents" / agent_base / "chroma"
            if self.skills_dir is None:
                self.skills_dir = settings.config_dir / "agents" / agent_base / "skills"
            if self.config_path is None:
                self.config_path = settings.config_dir / "agents" / agent_base / "agent.json"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert Path objects to strings
        for key in ['memory_db_path', 'chroma_path', 'skills_dir', 'config_path']:
            if data[key] is not None:
                data[key] = str(data[key])
        # Convert datetime to ISO format
        for key in ['created_at', 'updated_at', 'migrated_at']:
            if data[key] is not None:
                data[key] = data[key].isoformat() if isinstance(data[key], datetime) else data[key]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """Create Agent from dictionary."""
        # Convert string paths back to Path objects
        for key in ['memory_db_path', 'chroma_path', 'skills_dir', 'config_path']:
            if data.get(key) is not None:
                data[key] = Path(data[key])
        
        # Convert ISO format strings back to datetime
        for key in ['created_at', 'updated_at', 'migrated_at']:
            if data.get(key) is not None and isinstance(data[key], str):
                data[key] = datetime.fromisoformat(data[key])
        
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def ensure_directories(self):
        """Create all necessary directories for this agent."""
        paths = [
            self.memory_db_path.parent if self.memory_db_path else None,
            self.chroma_path if self.chroma_path else None,
            self.skills_dir if self.skills_dir else None,
            self.config_path.parent if self.config_path else None,
        ]
        for path in paths:
            if path is not None:
                path.mkdir(parents=True, exist_ok=True)
    
    def save(self):
        """Save agent configuration to disk."""
        if self.config_path is None:
            raise ValueError("Config path not set")
        
        self.ensure_directories()
        self.updated_at = datetime.now()
        
        self.config_path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
    
    @classmethod
    def load(cls, config_path: Path) -> 'Agent':
        """Load agent configuration from disk."""
        if not config_path.exists():
            raise FileNotFoundError(f"Agent config not found: {config_path}")
        
        data = json.loads(config_path.read_text(encoding='utf-8'))
        return cls.from_dict(data)
    
    @property
    def display_name(self) -> str:
        """Get display name with indicator if master."""
        if self.is_master:
            return f"{self.name} (主智能体)"
        return self.name


@dataclass
class AgentCreateRequest:
    """Request to create a new agent."""
    name: str
    description: str = ""
    personality: str = ""
    system_prompt: str = ""
    inherit_shared_skills: bool = True
    inherit_shared_tools: bool = True
    inherit_master_memories: bool = False


@dataclass
class AgentUpdateRequest:
    """Request to update an existing agent."""
    name: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    inherit_shared_skills: Optional[bool] = None
    inherit_shared_tools: Optional[bool] = None
    inherit_master_memories: Optional[bool] = None


@dataclass
class AgentSummary:
    """Summary of an agent for listing."""
    id: str
    name: str
    description: str
    is_master: bool
    is_active: bool
    created_at: datetime
    memory_count: int = 0
    skill_count: int = 0