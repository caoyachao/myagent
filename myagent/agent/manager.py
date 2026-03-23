"""Agent manager for CRUD operations and agent switching."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from myagent.agent.models import Agent, AgentCreateRequest, AgentUpdateRequest, AgentSummary
from myagent.config import get_settings


# Global instance
_agent_manager_instance: Optional['AgentManager'] = None


def get_agent_manager() -> 'AgentManager':
    """Get or create global agent manager instance."""
    global _agent_manager_instance
    if _agent_manager_instance is None:
        _agent_manager_instance = AgentManager()
    return _agent_manager_instance


class AgentManager:
    """Manages all agents: CRUD, switching, and state persistence."""
    
    def __init__(self):
        self.settings = get_settings()
        self._agents: Dict[str, Agent] = {}
        self._current_agent_id: Optional[str] = None
        
        # Initialize directories
        self._init_directories()
        
        # Load agents
        self._load_all_agents()
        
        # Ensure master agent exists
        self._ensure_master_agent()
        
        # Load current agent from state
        self._load_current_agent_state()
    
    def _init_directories(self):
        """Create necessary directories."""
        dirs = [
            self.settings.data_dir / "master",
            self.settings.data_dir / "agents",
            self.settings.config_dir / "shared_skills",
            self.settings.config_dir / "agents",
            self.settings.config_dir / "master",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
    
    def _ensure_master_agent(self):
        """Ensure master agent exists."""
        master_id = "master"
        
        if master_id not in self._agents:
            # Create master agent
            master = Agent(
                id=master_id,
                name="默认助手",
                description="系统主智能体，拥有所有共享技能和基础记忆",
                personality="全能助手，熟悉用户的所有历史和偏好",
                system_prompt="",
                inherit_shared_skills=True,
                inherit_shared_tools=True,
                inherit_master_memories=True,
                is_master=True,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            master.save()
            self._agents[master_id] = master
            self._current_agent_id = master_id
            self._save_current_agent_state()
    
    def _load_all_agents(self):
        """Load all agents from config directory."""
        self._agents = {}
        
        # Load master agent
        master_config = self.settings.config_dir / "master" / "agent.json"
        if master_config.exists():
            try:
                master = Agent.load(master_config)
                self._agents[master.id] = master
            except Exception as e:
                print(f"Failed to load master agent: {e}")
        
        # Load regular agents
        agents_dir = self.settings.config_dir / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    config_file = agent_dir / "agent.json"
                    if config_file.exists():
                        try:
                            agent = Agent.load(config_file)
                            self._agents[agent.id] = agent
                        except Exception as e:
                            print(f"Failed to load agent from {agent_dir}: {e}")
    
    def _load_current_agent_state(self):
        """Load current agent ID from state file."""
        state_file = self.settings.data_dir / "current_agent.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                agent_id = data.get("current_agent_id")
                if agent_id and agent_id in self._agents:
                    self._current_agent_id = agent_id
                    # Update active flag
                    for aid, agent in self._agents.items():
                        agent.is_active = (aid == agent_id)
                else:
                    # Default to master
                    self._current_agent_id = "master"
                    self._agents["master"].is_active = True
            except Exception:
                self._current_agent_id = "master"
                self._agents["master"].is_active = True
        else:
            self._current_agent_id = "master"
            self._agents["master"].is_active = True
    
    def _save_current_agent_state(self):
        """Save current agent ID to state file."""
        state_file = self.settings.data_dir / "current_agent.json"
        state_file.write_text(json.dumps({
            "current_agent_id": self._current_agent_id,
            "updated_at": datetime.now().isoformat()
        }, indent=2))
    
    def create_agent(self, request: AgentCreateRequest) -> Agent:
        """Create a new agent."""
        import uuid
        
        agent_id = str(uuid.uuid4())[:8]
        
        agent = Agent(
            id=agent_id,
            name=request.name,
            description=request.description,
            personality=request.personality,
            system_prompt=request.system_prompt,
            inherit_shared_skills=request.inherit_shared_skills,
            inherit_shared_tools=request.inherit_shared_tools,
            inherit_master_memories=request.inherit_master_memories,
            is_master=False,
            is_active=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Create directories and save config
        agent.ensure_directories()
        agent.save()
        
        # Initialize empty memory database for this agent
        self._init_agent_memory_db(agent)
        
        # Add to registry
        self._agents[agent_id] = agent
        
        return agent
    
    def _init_agent_memory_db(self, agent: Agent):
        """Initialize empty SQLite database for agent memory."""
        if agent.memory_db_path is None:
            return
        
        with sqlite3.connect(agent.memory_db_path) as conn:
            # Use string formatting for DEFAULT value (SQLite doesn't support params in CREATE TABLE)
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    agent_id TEXT DEFAULT '{agent.id}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    tags TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)")
            
            # Create metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _myagent_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Mark schema version
            conn.execute("""
                INSERT OR REPLACE INTO _myagent_meta (key, value) 
                VALUES ('schema_version', '2.0')
            """)
            
            conn.commit()
    
    def list_agents(self) -> List[AgentSummary]:
        """List all agents with summary info."""
        summaries = []
        
        for agent in self._agents.values():
            # Count memories
            memory_count = self._count_memories(agent)
            
            # Count skills
            skill_count = self._count_skills(agent)
            
            summaries.append(AgentSummary(
                id=agent.id,
                name=agent.name,
                description=agent.description,
                is_master=agent.is_master,
                is_active=agent.is_active,
                created_at=agent.created_at,
                memory_count=memory_count,
                skill_count=skill_count
            ))
        
        # Sort: master first, then by creation time
        summaries.sort(key=lambda x: (not x.is_master, x.created_at))
        
        return summaries
    
    def _count_memories(self, agent: Agent) -> int:
        """Count memories for an agent."""
        if agent.memory_db_path is None or not agent.memory_db_path.exists():
            return 0
        
        try:
            with sqlite3.connect(agent.memory_db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM memories")
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def _count_skills(self, agent: Agent) -> int:
        """Count private skills for an agent."""
        if agent.skills_dir is None or not agent.skills_dir.exists():
            return 0
        
        try:
            return len([d for d in agent.skills_dir.iterdir() if d.is_dir()])
        except Exception:
            return 0
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)
    
    def get_current_agent(self) -> Agent:
        """Get currently active agent."""
        if self._current_agent_id is None:
            self._current_agent_id = "master"
        
        agent = self._agents.get(self._current_agent_id)
        if agent is None:
            # Fallback to master
            agent = self._agents.get("master")
            if agent is None:
                raise RuntimeError("No master agent found")
            self._current_agent_id = "master"
        
        return agent
    
    def switch_agent(self, agent_id: str) -> Agent:
        """Switch to a different agent."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent not found: {agent_id}")
        
        # Deactivate current
        if self._current_agent_id:
            current = self._agents.get(self._current_agent_id)
            if current:
                current.is_active = False
        
        # Activate new
        self._current_agent_id = agent_id
        new_agent = self._agents[agent_id]
        new_agent.is_active = True
        
        # Save state
        self._save_current_agent_state()
        
        return new_agent
    
    def update_agent(self, agent_id: str, request: AgentUpdateRequest) -> Agent:
        """Update an existing agent."""
        if agent_id not in self._agents:
            raise ValueError(f"Agent not found: {agent_id}")
        
        agent = self._agents[agent_id]
        
        # Cannot update master agent's core properties
        if agent.is_master:
            if request.name is not None or request.personality is not None:
                raise PermissionError("Cannot modify master agent's name or personality")
        
        # Update fields
        if request.name is not None:
            agent.name = request.name
        if request.description is not None:
            agent.description = request.description
        if request.personality is not None:
            agent.personality = request.personality
        if request.system_prompt is not None:
            agent.system_prompt = request.system_prompt
        if request.inherit_shared_skills is not None:
            agent.inherit_shared_skills = request.inherit_shared_skills
        if request.inherit_shared_tools is not None:
            agent.inherit_shared_tools = request.inherit_shared_tools
        if request.inherit_master_memories is not None:
            agent.inherit_master_memories = request.inherit_master_memories
        
        agent.updated_at = datetime.now()
        agent.save()
        
        return agent
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent (only marks for deletion, actual cleanup done by cleaner)."""
        if agent_id not in self._agents:
            return False
        
        agent = self._agents[agent_id]
        
        # Cannot delete master
        if agent.is_master:
            raise PermissionError("Cannot delete master agent")
        
        # If currently active, switch to master first
        if self._current_agent_id == agent_id:
            self.switch_agent("master")
        
        # Remove from registry
        del self._agents[agent_id]
        
        return True
    
    def get_agent_memory_db_path(self, agent_id: str) -> Optional[Path]:
        """Get memory database path for an agent."""
        agent = self._agents.get(agent_id)
        if agent:
            return agent.memory_db_path
        return None
    
    def get_agent_chroma_path(self, agent_id: str) -> Optional[Path]:
        """Get chroma path for an agent."""
        agent = self._agents.get(agent_id)
        if agent:
            return agent.chroma_path
        return None
    
    def get_agent_skills_dir(self, agent_id: str) -> Optional[Path]:
        """Get skills directory for an agent."""
        agent = self._agents.get(agent_id)
        if agent:
            if agent.is_master:
                return self.settings.config_dir / "shared_skills"
            return agent.skills_dir
        return None