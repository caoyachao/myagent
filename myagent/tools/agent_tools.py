"""Agent management tools for MyAgent 2.0."""

import shutil
import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from myagent.agent.manager import AgentManager


class AgentTools:
    """Tools for managing agents."""
    
    def __init__(self, agent_manager: "AgentManager"):
        self.agent_manager = agent_manager
    
    def list_agents(self) -> str:
        """List all agents."""
        agents = self.agent_manager.list_agents()
        
        if not agents:
            return "No agents found."
        
        lines = [f"Available agents ({len(agents)}):\n"]
        
        for agent in agents:
            active_marker = " ★当前" if agent.is_active else ""
            master_marker = " [主智能体]" if agent.is_master else ""
            
            lines.append(f"• {agent.name}{master_marker}{active_marker}")
            lines.append(f"  ID: {agent.id}")
            lines.append(f"  Description: {agent.description}")
            lines.append(f"  Memories: {agent.memory_count} | Skills: {agent.skill_count}")
            lines.append("")
        
        lines.append("Use switch_agent(agent_id) to switch to a different agent.")
        
        return "\n".join(lines)
    
    def switch_agent(self, agent_id: str) -> str:
        """Switch to a different agent."""
        # Check if agent exists
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found. Use list_agents() to see available agents."
        
        # Check if already active
        current = self.agent_manager.get_current_agent()
        if current.id == agent_id:
            return f"Already using agent '{agent.name}'."
        
        # Perform switch
        new_agent = self.agent_manager.switch_agent(agent_id)
        
        return f"""Switched to agent '{new_agent.name}'.

人格：{new_agent.personality or '无'}
描述：{new_agent.description or '无'}

Tip: This agent has {new_agent.inherit_shared_skills and 'access to' or 'no access to'} shared skills.
"""
    
    def create_agent(
        self,
        name: str,
        description: str = "",
        personality: str = "",
        system_prompt: str = "",
        inherit_shared_skills: bool = True,
        inherit_shared_tools: bool = True,
        inherit_master_memories: bool = False
    ) -> str:
        """Create a new agent."""
        from myagent.agent.models import AgentCreateRequest
        
        # Validate name
        if not name or len(name.strip()) == 0:
            return "Error: Agent name cannot be empty."
        
        # Check for duplicate names
        existing = self.agent_manager.list_agents()
        if any(a.name == name for a in existing):
            return f"Error: An agent with name '{name}' already exists."
        
        request = AgentCreateRequest(
            name=name.strip(),
            description=description,
            personality=personality,
            system_prompt=system_prompt,
            inherit_shared_skills=inherit_shared_skills,
            inherit_shared_tools=inherit_shared_tools,
            inherit_master_memories=inherit_master_memories
        )
        
        try:
            agent = self.agent_manager.create_agent(request)
            
            return f"""✅ Agent '{agent.name}' created successfully!

ID: {agent.id}
Name: {agent.name}
Description: {agent.description or 'None'}
Personality: {agent.personality or 'None'}

Inheritance settings:
- Shared skills: {'Yes' if inherit_shared_skills else 'No'}
- Shared tools: {'Yes' if inherit_shared_tools else 'No'}
- Master memories: {'Yes' if inherit_master_memories else 'No'}

Use switch_agent("{agent.id}") to start using this agent.
"""
        except Exception as e:
            return f"Error creating agent: {str(e)}"
    
    def delete_agent(self, agent_id: str) -> str:
        """Delete an agent."""
        # Get agent info before deletion
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found."
        
        if agent.is_master:
            return "Error: Cannot delete the master agent."
        
        agent_name = agent.name
        
        # Check if currently active
        current = self.agent_manager.get_current_agent()
        was_active = current.id == agent_id
        
        try:
            # Delete agent from manager
            self.agent_manager.delete_agent(agent_id)
            
            # Perform full cleanup
            from myagent.agent.cleaner import AgentCleaner
            cleaner = AgentCleaner(self.agent_manager)
            stats = cleaner.cleanup_agent_data(agent)
            
            result = f"Agent '{agent_name}' deleted successfully.\n\n"
            result += f"Cleaned up:\n"
            result += f"- Memory database: {stats.memory_deleted}\n"
            result += f"- Chroma files: {stats.chroma_files_deleted}\n"
            result += f"- Private skills: {stats.skills_deleted}\n"
            result += f"- Config files: {stats.config_deleted}\n"
            
            if was_active:
                result += f"\nAutomatically switched back to master agent."
            
            return result
            
        except Exception as e:
            return f"Error deleting agent: {str(e)}"
    
    def get_current_info(self) -> str:
        """Get information about current agent."""
        agent = self.agent_manager.get_current_agent()
        
        # Get memory stats
        memory_count = 0
        if agent.memory_db_path and agent.memory_db_path.exists():
            import sqlite3
            try:
                with sqlite3.connect(agent.memory_db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM memories")
                    memory_count = cursor.fetchone()[0]
            except Exception:
                pass
        
        # Get skill count
        skill_count = 0
        if agent.skills_dir and agent.skills_dir.exists():
            skill_count = len([d for d in agent.skills_dir.iterdir() if d.is_dir()])
        
        lines = [
            f"Current Agent: {agent.name}",
            f"ID: {agent.id}",
            f"Description: {agent.description or 'None'}",
        ]
        
        if agent.personality:
            lines.append(f"Personality: {agent.personality}")
        
        lines.extend([
            f"",
            f"Statistics:",
            f"- Memories: {memory_count}",
            f"- Private skills: {skill_count}",
            f"",
            f"Inheritance:",
            f"- Shared skills: {'Yes' if agent.inherit_shared_skills else 'No'}",
            f"- Shared tools: {'Yes' if agent.inherit_shared_tools else 'No'}",
            f"- Master memories: {'Yes' if agent.inherit_master_memories else 'No'}",
        ])
        
        if agent.is_master:
            lines.append(f"\nThis is the master agent.")
        
        return "\n".join(lines)
    
    def create_agent_from(
        self,
        source_agent_id: str,
        new_name: str,
        new_description: str = "",
        copy_memories: bool = True,
        copy_skills: bool = True,
        copy_personality: bool = True
    ) -> str:
        """Create a new agent by copying from an existing agent.
        
        This creates a perfect clone including memories, skills, and personality.
        
        Args:
            source_agent_id: ID of the agent to copy from
            new_name: Name for the new agent
            new_description: Optional new description (defaults to source's description)
            copy_memories: Whether to copy all memories (default: True)
            copy_skills: Whether to copy all private skills (default: True)
            copy_personality: Whether to copy personality and system prompt (default: True)
        """
        from myagent.agent.models import AgentCreateRequest
        
        # Validate new name
        if not new_name or len(new_name.strip()) == 0:
            return "Error: New agent name cannot be empty."
        
        # Check for duplicate names
        existing = self.agent_manager.list_agents()
        if any(a.name == new_name for a in existing):
            return f"Error: An agent with name '{new_name}' already exists."
        
        # Get source agent
        source_agent = self.agent_manager.get_agent(source_agent_id)
        if not source_agent:
            return f"Error: Source agent '{source_agent_id}' not found."
        
        if source_agent.is_master:
            return "Error: Cannot clone from master agent. Use create_agent instead."
        
        # Determine attributes
        description = new_description or source_agent.description
        personality = source_agent.personality if copy_personality else ""
        system_prompt = source_agent.system_prompt if copy_personality else ""
        
        try:
            # Create new agent
            request = AgentCreateRequest(
                name=new_name.strip(),
                description=description,
                personality=personality,
                system_prompt=system_prompt,
                inherit_shared_skills=source_agent.inherit_shared_skills,
                inherit_shared_tools=source_agent.inherit_shared_tools,
                inherit_master_memories=source_agent.inherit_master_memories
            )
            
            new_agent = self.agent_manager.create_agent(request)
            
            # Copy memories if requested
            memory_count = 0
            if copy_memories and source_agent.memory_db_path and source_agent.memory_db_path.exists():
                memory_count = self._copy_memories(source_agent, new_agent)
            
            # Copy skills if requested
            skill_count = 0
            if copy_skills and source_agent.skills_dir and source_agent.skills_dir.exists():
                skill_count = self._copy_skills(source_agent, new_agent)
            
            # Get final stats
            final_memory_count = 0
            if new_agent.memory_db_path and new_agent.memory_db_path.exists():
                try:
                    with sqlite3.connect(new_agent.memory_db_path) as conn:
                        cursor = conn.execute("SELECT COUNT(*) FROM memories")
                        final_memory_count = cursor.fetchone()[0]
                except Exception:
                    pass
            
            final_skill_count = 0
            if new_agent.skills_dir and new_agent.skills_dir.exists():
                final_skill_count = len([d for d in new_agent.skills_dir.iterdir() if d.is_dir()])
            
            return f"""✅ Agent '{new_agent.name}' created successfully from '{source_agent.name}'!

📋 Basic Info:
ID: {new_agent.id}
Name: {new_agent.name}
Description: {new_agent.description or 'None'}
Personality: {new_agent.personality or 'None'}

📦 Copied Data:
- Memories: {memory_count} copied (total: {final_memory_count})
- Private Skills: {skill_count} copied (total: {final_skill_count})
- Shared Skills: {'Inherited' if new_agent.inherit_shared_skills else 'Not inherited'}

⚙️ Inheritance Settings:
- Shared skills: {'Yes' if new_agent.inherit_shared_skills else 'No'}
- Shared tools: {'Yes' if new_agent.inherit_shared_tools else 'No'}
- Master memories: {'Yes' if new_agent.inherit_master_memories else 'No'}

💡 Usage:
Use switch_agent("{new_agent.id}") to start using this agent.
The new agent is an independent copy - changes won't affect the original.
"""
        except Exception as e:
            return f"Error creating agent from '{source_agent.name}': {str(e)}"
    
    def _copy_memories(self, source_agent, new_agent) -> int:
        """Copy all memories from source agent to new agent."""
        if not source_agent.memory_db_path or not source_agent.memory_db_path.exists():
            return 0
        
        if not new_agent.memory_db_path:
            return 0
        
        count = 0
        try:
            # Read all memories from source
            with sqlite3.connect(source_agent.memory_db_path) as source_conn:
                source_conn.row_factory = sqlite3.Row
                rows = source_conn.execute(
                    "SELECT * FROM memories WHERE agent_id = ?",
                    (source_agent.id,)
                ).fetchall()
            
            if not rows:
                return 0
            
            # Insert into new agent's database
            with sqlite3.connect(new_agent.memory_db_path) as dest_conn:
                for row in rows:
                    dest_conn.execute(
                        """INSERT INTO memories 
                           (id, content, memory_type, source, agent_id, created_at, updated_at, 
                            access_count, last_accessed, tags, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            row["id"], row["content"], row["memory_type"], 
                            f"{row['source']} (copied from {source_agent.name})",
                            new_agent.id, row["created_at"], row["updated_at"],
                            row["access_count"], row["last_accessed"], 
                            row["tags"], row["metadata"]
                        )
                    )
                    count += 1
                dest_conn.commit()
            
            # Copy Chroma embeddings
            if source_agent.chroma_path and source_agent.chroma_path.exists():
                self._copy_chroma_embeddings(source_agent, new_agent, rows)
            
            return count
        except Exception as e:
            print(f"Warning: Failed to copy some memories: {e}")
            return count
    
    def _copy_chroma_embeddings(self, source_agent, new_agent, memory_rows):
        """Copy Chroma embeddings for memories."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            # Source client
            source_client = chromadb.PersistentClient(
                path=str(source_agent.chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            source_collection = source_client.get_collection(f"memories_{source_agent.id}")
            
            # Dest client
            dest_client = chromadb.PersistentClient(
                path=str(new_agent.chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            dest_collection = dest_client.get_or_create_collection(
                name=f"memories_{new_agent.id}",
                metadata={
                    "hnsw:space": "cosine",
                    "agent_id": new_agent.id
                }
            )
            
            # Copy embeddings in batches
            memory_ids = [row["id"] for row in memory_rows]
            batch_size = 100
            
            for i in range(0, len(memory_ids), batch_size):
                batch_ids = memory_ids[i:i + batch_size]
                try:
                    results = source_collection.get(ids=batch_ids)
                    if results and results["ids"]:
                        dest_collection.add(
                            ids=results["ids"],
                            documents=results["documents"],
                            metadatas=[{
                                **m,
                                "agent_id": new_agent.id,
                                "source": f"{m.get('source', '')} (copied from {source_agent.name})"
                            } for m in results["metadatas"]],
                            embeddings=results.get("embeddings")
                        )
                except Exception as e:
                    print(f"Warning: Failed to copy embeddings batch: {e}")
        except Exception as e:
            print(f"Warning: Failed to copy Chroma embeddings: {e}")
    
    def _copy_skills(self, source_agent, new_agent) -> int:
        """Copy all private skills from source agent to new agent."""
        if not source_agent.skills_dir or not source_agent.skills_dir.exists():
            return 0
        
        if not new_agent.skills_dir:
            return 0
        
        count = 0
        try:
            # Ensure destination directory exists
            new_agent.skills_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy each skill directory
            for skill_dir in source_agent.skills_dir.iterdir():
                if skill_dir.is_dir():
                    dest_skill_dir = new_agent.skills_dir / skill_dir.name
                    if dest_skill_dir.exists():
                        shutil.rmtree(dest_skill_dir)
                    shutil.copytree(skill_dir, dest_skill_dir)
                    count += 1
            
            return count
        except Exception as e:
            print(f"Warning: Failed to copy some skills: {e}")
            return count
    
    def rename_agent(self, agent_id: str, new_name: str) -> str:
        """Rename an agent without losing any data.
        
        Only the display name is changed. All memories, skills, and tools remain intact.
        
        Args:
            agent_id: ID of the agent to rename
            new_name: New name for the agent
        """
        # Validate new name
        if not new_name or len(new_name.strip()) == 0:
            return "Error: New name cannot be empty."
        
        new_name = new_name.strip()
        
        # Check for duplicate names
        existing = self.agent_manager.list_agents()
        if any(a.name == new_name and a.id != agent_id for a in existing):
            return f"Error: An agent with name '{new_name}' already exists."
        
        # Get agent
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return f"Error: Agent '{agent_id}' not found."
        
        if agent.is_master:
            return "Error: Cannot rename the master agent."
        
        old_name = agent.name
        
        try:
            # Update name
            agent.name = new_name
            agent.updated_at = __import__('datetime').datetime.now()
            
            # Save to disk
            agent.save()
            
            # Update in-memory agent
            self.agent_manager._agents[agent_id] = agent
            
            return f"""✅ Agent renamed successfully!

📋 Rename Details:
   Old Name: {old_name}
   New Name: {agent.name}
   ID:       {agent.id}

📦 Data Preserved:
   ✅ All {self._count_agent_memories(agent)} memories
   ✅ All {self._count_agent_skills(agent)} private skills
   ✅ All personality settings
   ✅ All configuration

💡 Note: Only the display name was changed. All data paths remain the same.
"""
        except Exception as e:
            return f"Error renaming agent: {str(e)}"
    
    def _count_agent_memories(self, agent) -> int:
        """Count memories for an agent."""
        if not agent.memory_db_path or not agent.memory_db_path.exists():
            return 0
        try:
            with sqlite3.connect(agent.memory_db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE agent_id = ?", (agent.id,))
                return cursor.fetchone()[0]
        except Exception:
            return 0
    
    def _count_agent_skills(self, agent) -> int:
        """Count private skills for an agent."""
        if not agent.skills_dir or not agent.skills_dir.exists():
            return 0
        try:
            return len([d for d in agent.skills_dir.iterdir() if d.is_dir()])
        except Exception:
            return 0
    
    def show_agent_info(self, agent_id: str) -> str:
        """Show detailed information about a specific agent."""
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return f"Error: Agent '{agent_id}' not found."
        
        # Get memory stats
        memory_count = 0
        memory_by_type = {}
        if agent.memory_db_path and agent.memory_db_path.exists():
            try:
                with sqlite3.connect(agent.memory_db_path) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM memories WHERE agent_id = ?", (agent.id,))
                    memory_count = cursor.fetchone()[0]
                    
                    # Get breakdown by type
                    for row in conn.execute(
                        "SELECT memory_type, COUNT(*) FROM memories WHERE agent_id = ? GROUP BY memory_type",
                        (agent.id,)
                    ):
                        memory_by_type[row[0]] = row[1]
            except Exception:
                pass
        
        # Get skill details
        skills = []
        if agent.skills_dir and agent.skills_dir.exists():
            for skill_dir in agent.skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        skills.append(skill_dir.name)
        
        # Build info display
        lines = [
            f"╔══════════════════════════════════════════════════════════════╗",
            f"║  Agent Information: {agent.name:<41} ║",
            f"╚══════════════════════════════════════════════════════════════╝",
            f"",
            f"📋 Basic Information:",
            f"   ID:          {agent.id}",
            f"   Name:        {agent.name}",
            f"   Type:        {'Master Agent' if agent.is_master else 'Regular Agent'}",
            f"   Description: {agent.description or 'None'}",
            f"",
            f"🎭 Personality & Settings:",
            f"   Personality: {agent.personality or 'None'}",
            f"   System Prompt: {agent.system_prompt[:50] + '...' if agent.system_prompt and len(agent.system_prompt) > 50 else (agent.system_prompt or 'None')}",
            f"",
            f"📊 Statistics:",
            f"   Total Memories: {memory_count}",
        ]
        
        if memory_by_type:
            lines.append(f"   By Type:")
            for mem_type, count in sorted(memory_by_type.items()):
                lines.append(f"      - {mem_type}: {count}")
        
        lines.extend([
            f"   Private Skills: {len(skills)}",
        ])
        
        if skills:
            for skill in skills:
                lines.append(f"      - {skill}")
        
        lines.extend([
            f"",
            f"⚙️ Inheritance Settings:",
            f"   Shared Skills:   {'✅ Yes' if agent.inherit_shared_skills else '❌ No'}",
            f"   Shared Tools:    {'✅ Yes' if agent.inherit_shared_tools else '❌ No'}",
            f"   Master Memories: {'✅ Yes' if agent.inherit_master_memories else '❌ No'}",
            f"",
            f"📁 Storage Paths:",
            f"   Config:  {agent.config_path}",
            f"   Memory:  {agent.memory_db_path}",
            f"   Skills:  {agent.skills_dir}",
            f"   Chroma:  {agent.chroma_path}",
            f"",
            f"📅 Metadata:",
            f"   Created: {agent.created_at.strftime('%Y-%m-%d %H:%M:%S') if agent.created_at else 'Unknown'}",
            f"   Updated: {agent.updated_at.strftime('%Y-%m-%d %H:%M:%S') if agent.updated_at else 'Unknown'}",
        ])
        
        if agent.migrated_from_v1:
            lines.append(f"   Migrated from v1: {agent.migrated_at.strftime('%Y-%m-%d %H:%M:%S') if agent.migrated_at else 'Yes'}")
        
        lines.append(f"")
        
        return "\n".join(lines)