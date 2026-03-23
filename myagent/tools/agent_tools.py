"""Agent management tools for MyAgent 2.0."""

from typing import TYPE_CHECKING

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