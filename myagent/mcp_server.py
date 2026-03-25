"""MCP Server for MyAgent 2.0 - Multi-Agent support."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource

from myagent.config import get_settings
from myagent.agent.manager import AgentManager, get_agent_manager
from myagent.agent.models import AgentCreateRequest
from myagent.memory.agent_store import AgentAwareMemoryStore
from myagent.skills.agent_registry import AgentAwareSkillRegistry
from myagent.tools.agent_tools import AgentTools
from myagent.tools.memory_tools_v2 import MemoryToolsV2


class AgentAwareMCPServer:
    """MCP Server with multi-agent support.
    
    Each MCP session starts with 'master' agent by default.
    Agent switching is session-level only and does not persist across sessions.
    This enables multiple windows to run different agents simultaneously.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.server = Server(self.settings.mcp_server_name)
        self.agent_manager = get_agent_manager()
        
        # Session-level current agent (always start with master)
        self.session_agent_id = "master"
        
        # Initialize current agent's stores
        self._refresh_agent_context()
        
        # Setup handlers
        self._setup_handlers()
    
    def _refresh_agent_context(self):
        """Refresh context for current agent (session-level)."""
        # Use session-level agent ID instead of global current agent
        agent = self.agent_manager.get_agent(self.session_agent_id)
        if agent is None:
            # Fallback to master if session agent not found
            agent = self.agent_manager.get_agent("master")
            self.session_agent_id = "master"
        
        self.current_agent = agent
        # Pass explicit agent_id to ensure memory is stored in the correct agent's database
        self.memory_store = AgentAwareMemoryStore(self.agent_manager, agent_id=self.session_agent_id)
        self.skill_registry = AgentAwareSkillRegistry(self.current_agent, self.agent_manager)
        
        # Initialize tool handlers
        self.agent_tools = AgentTools(self.agent_manager)
        self.memory_tools = MemoryToolsV2(self.memory_store, self.current_agent)
    
    def _setup_handlers(self):
        """Setup MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools for current agent."""
            tools = []
            
            # Add memory management tools
            tools.extend(self._get_memory_tools())
            
            # Add agent management tools
            tools.extend(self._get_agent_management_tools())
            
            # Add skill management tools
            tools.extend(self._get_skill_management_tools())
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a tool."""
            try:
                # Refresh context in case agent was switched
                self._refresh_agent_context()
                
                result = await self._execute_tool(name, arguments)
                
                # Wrap result with agent name
                wrapped_result = self._wrap_with_agent(result)
                return [TextContent(type="text", text=wrapped_result)]
                
            except Exception as e:
                error_msg = self._wrap_with_agent(f"错误：{str(e)}")
                return [TextContent(type="text", text=error_msg)]
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available resources."""
            resources = []
            
            # Add system prompt as a resource
            resources.append(Resource(
                uri="myagent://system-prompt",
                name="Enhanced System Prompt",
                mimeType="text/markdown",
                description=f"System prompt for {self.current_agent.name} with memory and skills context"
            ))
            
            # Add memory stats resource
            resources.append(Resource(
                uri="myagent://memory-stats",
                name="Memory Statistics",
                mimeType="application/json",
                description=f"Current memory store statistics for {self.current_agent.name}"
            ))
            
            # Add current agent info resource
            resources.append(Resource(
                uri="myagent://current-agent",
                name="Current Agent Info",
                mimeType="application/json",
                description="Information about the currently active agent"
            ))
            
            return resources
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource."""
            # Refresh context
            self._refresh_agent_context()
            
            if uri == "myagent://system-prompt":
                return self._assemble_system_prompt()
            
            elif uri == "myagent://memory-stats":
                stats = self.memory_store.get_stats()
                return self._wrap_with_agent(json.dumps(stats, indent=2, ensure_ascii=False))
            
            elif uri == "myagent://current-agent":
                agent_info = {
                    "id": self.current_agent.id,
                    "name": self.current_agent.name,
                    "description": self.current_agent.description,
                    "personality": self.current_agent.personality,
                    "is_master": self.current_agent.is_master,
                    "inherit_shared_skills": self.current_agent.inherit_shared_skills,
                    "inherit_shared_tools": self.current_agent.inherit_shared_tools,
                    "inherit_master_memories": self.current_agent.inherit_master_memories,
                }
                return self._wrap_with_agent(json.dumps(agent_info, indent=2, ensure_ascii=False))
            
            else:
                raise ValueError(f"Unknown resource: {uri}")
    
    def _get_memory_tools(self) -> List[Tool]:
        """Get memory management tools."""
        return [
            Tool(
                name="recall_memory",
                description="Search and retrieve relevant memories based on a query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query"},
                        "top_k": {"type": "integer", "default": 5, "description": "Number of memories to retrieve"},
                        "memory_type": {"type": "string", "description": "Filter by memory type"},
                        "include_master": {"type": "boolean", "description": "Include master agent memories (overrides default)"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="save_memory",
                description="Save important information to current agent's memory. IMPORTANT: By default, memories are ONLY saved to the current agent and will NOT be shared with master. Use share_with_master=true only when explicitly requested by user.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The information to save"},
                        "memory_type": {"type": "string", "default": "fact", "description": "Type of memory: fact, preference, event, insight, code, secret"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tags for categorization"},
                        "share_with_master": {"type": "boolean", "default": False, "description": "EXPLICIT ONLY: Also save to master agent. Default is false - memories stay in current agent only."}
                    },
                    "required": ["content"]
                }
            ),
            Tool(
                name="list_recent_memories",
                description="List recently added memories",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10},
                        "memory_type": {"type": "string"}
                    }
                }
            ),
            Tool(
                name="forget_memory",
                description="Delete a memory by its ID",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {"type": "string"}
                    },
                    "required": ["memory_id"]
                }
            ),
            Tool(
                name="get_memory_stats",
                description="Get statistics about the memory store",
                inputSchema={"type": "object"}
            ),
        ]
    
    def _get_agent_management_tools(self) -> List[Tool]:
        """Get agent management tools."""
        return [
            Tool(
                name="list_agents",
                description="List all available agents",
                inputSchema={"type": "object"}
            ),
            Tool(
                name="switch_agent",
                description="Switch to a different agent",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "ID of the agent to switch to"}
                    },
                    "required": ["agent_id"]
                }
            ),
            Tool(
                name="create_agent",
                description="Create a new agent with custom personality",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the agent"},
                        "description": {"type": "string", "description": "Description of the agent"},
                        "personality": {"type": "string", "description": "Personality traits"},
                        "system_prompt": {"type": "string", "description": "Additional system prompt"},
                        "inherit_shared_skills": {"type": "boolean", "default": True},
                        "inherit_shared_tools": {"type": "boolean", "default": True},
                        "inherit_master_memories": {"type": "boolean", "default": False}
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="create_agent_from",
                description="Create a new agent by copying from an existing agent, including all memories, skills, and personality",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_agent_id": {"type": "string", "description": "ID of the agent to copy from"},
                        "new_name": {"type": "string", "description": "Name for the new agent"},
                        "new_description": {"type": "string", "description": "Optional new description (defaults to source's description)"},
                        "copy_memories": {"type": "boolean", "default": True, "description": "Whether to copy all memories"},
                        "copy_skills": {"type": "boolean", "default": True, "description": "Whether to copy all private skills"},
                        "copy_personality": {"type": "boolean", "default": True, "description": "Whether to copy personality and system prompt"}
                    },
                    "required": ["source_agent_id", "new_name"]
                }
            ),
            Tool(
                name="show_agent_info",
                description="Show detailed information about a specific agent including memories, skills, and settings",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "ID of the agent to show info for"}
                    },
                    "required": ["agent_id"]
                }
            ),
            Tool(
                name="rename_agent",
                description="Rename an agent without losing any memories, skills, or tools",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "ID of the agent to rename"},
                        "new_name": {"type": "string", "description": "New name for the agent"}
                    },
                    "required": ["agent_id", "new_name"]
                }
            ),
            Tool(
                name="delete_agent",
                description="Delete an agent (cannot delete master agent)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string", "description": "ID of the agent to delete"}
                    },
                    "required": ["agent_id"]
                }
            ),
            Tool(
                name="get_current_agent_info",
                description="Get information about the current agent",
                inputSchema={"type": "object"}
            ),
        ]
    
    def _get_skill_management_tools(self) -> List[Tool]:
        """Get skill management tools."""
        return [
            Tool(
                name="list_skills",
                description="List available skills for current agent",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "include_private": {"type": "boolean", "default": True}
                    }
                }
            ),
            Tool(
                name="get_skill_info",
                description="Get detailed information about a skill",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skill_name": {"type": "string"}
                    },
                    "required": ["skill_name"]
                }
            ),
            Tool(
                name="reload_skills",
                description="Reload all skills from disk",
                inputSchema={"type": "object"}
            ),
        ]
    
    async def _execute_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Execute a tool by name."""
        # Memory tools
        if name == "recall_memory":
            return self.memory_tools.recall(**arguments)
        elif name == "save_memory":
            return self.memory_tools.save(**arguments)
        elif name == "list_recent_memories":
            return self.memory_tools.list_recent(**arguments)
        elif name == "forget_memory":
            return self.memory_tools.forget(**arguments)
        elif name == "get_memory_stats":
            return self.memory_tools.get_stats()
        
        # Agent management tools (session-level)
        elif name == "list_agents":
            return self._list_agents_session()
        elif name == "switch_agent":
            return self._switch_agent_session(**arguments)
        elif name == "create_agent":
            return self.agent_tools.create_agent(**arguments)
        elif name == "create_agent_from":
            return self.agent_tools.create_agent_from(**arguments)
        elif name == "show_agent_info":
            return self.agent_tools.show_agent_info(**arguments)
        elif name == "rename_agent":
            return self.agent_tools.rename_agent(**arguments)
        elif name == "delete_agent":
            return self.agent_tools.delete_agent(**arguments)
        elif name == "get_current_agent_info":
            return self._get_current_info_session()
        
        # Skill management tools
        elif name == "list_skills":
            return self._list_skills(**arguments)
        elif name == "get_skill_info":
            return self._get_skill_info(**arguments)
        elif name == "reload_skills":
            self.skill_registry.reload()
            return "Skills reloaded successfully."
        
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    def _list_agents_session(self) -> str:
        """List all agents with session-level current marker."""
        # 刷新智能体列表，确保看到其他会话创建的agent
        self.agent_manager._load_all_agents()
        agents = self.agent_manager.list_agents()
        
        if not agents:
            return "No agents found."
        
        lines = [f"Available agents ({len(agents)}):\n"]
        
        for agent_summary in agents:
            # Mark session agent as current
            is_session_current = (agent_summary.id == self.session_agent_id)
            active_marker = " ★当前会话" if is_session_current else ""
            master_marker = " [主智能体]" if agent_summary.is_master else ""
            
            lines.append(f"• {agent_summary.name}{master_marker}{active_marker}")
            lines.append(f"  ID: {agent_summary.id}")
            lines.append(f"  Description: {agent_summary.description}")
            lines.append(f"  Memories: {agent_summary.memory_count} | Skills: {agent_summary.skill_count}")
            lines.append("")
        
        lines.append("Use switch_agent(agent_id) to switch to a different agent (session only).")
        
        return "\n".join(lines)
    
    def _switch_agent_session(self, agent_id: str) -> str:
        """Switch to a different agent (session-level only)."""
        # Check if agent exists
        agent = self.agent_manager.get_agent(agent_id)
        if not agent:
            return f"Agent '{agent_id}' not found. Use list_agents() to see available agents."
        
        # Check if already active in this session
        if self.session_agent_id == agent_id:
            return f"Already using agent '{agent.name}' in this session."
        
        # Perform session-level switch (no persistence)
        self.session_agent_id = agent_id
        self._refresh_agent_context()
        
        return f"""【{agent.name}】Switched to agent '{agent.name}' (current session only).

人格：{agent.personality or '无'}
描述：{agent.description or '无'}

继承设置：
- 共享技能：{'是' if agent.inherit_shared_skills else '否'}
- 共享工具：{'是' if agent.inherit_shared_tools else '否'}
- 主智能体记忆：{'是' if agent.inherit_master_memories else '否'}

提示：此切换仅对当前会话有效。新窗口启动时仍将使用 master 智能体。
"""
    
    def _get_current_info_session(self) -> str:
        """Get information about current agent (session-level)."""
        agent = self.agent_manager.get_agent(self.session_agent_id)
        if not agent:
            return "Error: Current agent not found."
        
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
            f"Current Agent (Session): {agent.name}",
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
            f"",
            f"Note: This is the session-level current agent. New sessions start with 'master'.",
        ])
        
        if agent.is_master:
            lines.append(f"\nThis is the master agent.")
        
        return "\n".join(lines)
    
    def _list_skills(self, include_private: bool = True) -> str:
        """List available skills."""
        skills = self.skill_registry.list_all()
        
        if not skills:
            return "No skills available."
        
        lines = [f"Available skills ({len(skills)}):"]
        lines.append("(Priority: Project > Private > Shared)\n")
        
        for skill in skills:
            origin = self.skill_registry.get_skill_origin(skill.name)
            origin_marker = {
                'project': ' [📁项目]',
                'private': ' [🔒私有]',
                'shared': ' [🌐共享]'
            }.get(origin, '')
            
            lines.append(f"• {skill.name}{origin_marker}")
            lines.append(f"  {skill.description}")
            if skill.tools:
                lines.append(f"  Tools: {', '.join(skill.tools)}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _get_skill_origin_marker(self, skill_name: str) -> str:
        """Get origin marker for a skill."""
        origin = self.skill_registry.get_skill_origin(skill_name)
        return {
            'project': '📁项目',
            'private': '🔒私有', 
            'shared': '🌐共享'
        }.get(origin, '❓未知')
    
    def _get_skill_info(self, skill_name: str) -> str:
        """Get detailed info about a skill."""
        skill = self.skill_registry.get(skill_name)
        if not skill:
            return f"Skill '{skill_name}' not found."
        
        info = skill.info
        lines = [
            f"Skill: {info.name}",
            f"Description: {info.description}",
            f"Version: {info.version}",
        ]
        if info.author:
            lines.append(f"Author: {info.author}")
        if info.tags:
            lines.append(f"Tags: {', '.join(info.tags)}")
        if info.tools:
            lines.append(f"Tools: {', '.join(info.tools)}")
        if info.content:
            lines.append(f"\n{info.content}")
        
        return "\n".join(lines)
    
    def _assemble_system_prompt(self) -> str:
        """Assemble system prompt with agent identity."""
        agent = self.current_agent
        
        lines = [
            f"【{agent.name}】",
            "",
            self._get_agent_identity_section(),
            self._get_base_prompt(),
            self._get_format_instruction(),
        ]
        
        return "\n\n".join(lines)
    
    def _get_agent_identity_section(self) -> str:
        """Get agent identity section."""
        agent = self.current_agent
        lines = [
            "【你当前的身份】",
            f"名称：{agent.name}",
        ]
        if agent.description:
            lines.append(f"描述：{agent.description}")
        if agent.personality:
            lines.append(f"人格：{agent.personality}")
        
        lines.extend([
            "",
            "【继承设置】",
            f"- 共享技能：{'是' if agent.inherit_shared_skills else '否'}",
            f"- 共享工具：{'是' if agent.inherit_shared_tools else '否'}",
            f"- 主智能体记忆：{'是' if agent.inherit_master_memories else '否'}",
        ])
        
        if agent.system_prompt:
            lines.extend(["", "【额外指令】", agent.system_prompt])
        
        return "\n".join(lines)
    
    def _get_base_prompt(self) -> str:
        """Get base system prompt."""
        agent_name = self.current_agent.name
        is_master = self.current_agent.is_master
        
        memory_storage_rules = """
【记忆存储安全规则】⚠️ 重要
1. 默认只保存到当前智能体：save_memory 默认只保存到当前智能体的记忆库
2. 不自动共享到master：除非用户明确要求，否则绝不使用 share_with_master=true
3. 隔离原则：每个智能体的记忆是独立的，不应自动污染master的记忆库
4. 查询可跨智能体：recall_memory 默认可以查询当前智能体 + master 的记忆（只读）
""" if not is_master else """
【记忆存储规则】
当前是Master智能体，保存的记忆可以作为共享知识被其他智能体查询。
"""
        
        return f"""【基础指令】
你是一个有长期记忆的 AI 助手（当前身份：{agent_name}）。

{memory_storage_rules}

重要原则：
1. 主动检索相关记忆来提供个性化回复（recall_memory 可同时查自己和master）
2. 当用户提到过去的事情时，使用 recall_memory 工具检索
3. 重要信息使用 save_memory 保存（默认只保存到当前智能体，不共享）
4. 利用可用技能来更好地完成任务
5. 可以使用 create_agent 创建新智能体，switch_agent 切换智能体

记忆类型说明：
- fact: 客观事实和知识
- preference: 用户偏好和习惯
- event: 特定事件和经历
- insight: 洞察和总结
- code: 代码片段和技术方案
- secret: 敏感信息如token、密码等

⚠️ 安全提醒：
- 保存敏感信息（如GitHub token）时，考虑使用 memory_type="secret"
- 默认情况下，记忆只保存在当前智能体，不会自动同步到master"""
    
    def _get_format_instruction(self) -> str:
        """Get format instruction."""
        agent = self.current_agent
        return f"""【回复格式要求】
每次回复时，请严格遵循以下格式：
【{agent.name}】你的回复内容...

这样可以清楚地向用户表明当前是哪个智能体在回复。

示例：
【{agent.name}】你好！我是{agent.name}。有什么可以帮你的吗？"""
    
    def _wrap_with_agent(self, content: str) -> str:
        """Wrap content with agent name prefix."""
        agent_name = self.current_agent.name
        
        # If already starts with agent prefix, don't add again
        if content.startswith(f"【{agent_name}】"):
            return content
        
        # If starts with another agent's prefix, replace it
        if content.startswith("【") and "】" in content:
            import re
            content = re.sub(r"^【[^】]+】", "", content)
        
        return f"【{agent_name}】{content}"
    
    async def run(self):
        """Run the MCP server."""
        from mcp.server.stdio import stdio_server
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


def main():
    """Entry point for MCP server."""
    server = AgentAwareMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()