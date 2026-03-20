"""MCP Server for MyAgent - integrates with Kimi Code CLI."""

import asyncio
import json
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource

from myagent.config import get_settings
from myagent.memory.store import MemoryStore, get_memory_store
from myagent.skills.registry import SkillRegistry, get_skill_registry
from myagent.tools.registry import ToolRegistry, get_tool_registry
from myagent.prompt.assembler import PromptAssembler

# Import tools to register them
from myagent.tools import memory_tools, skill_tools


class MyAgentMCPServer:
    """MCP Server that provides memory and skill capabilities."""
    
    def __init__(self):
        self.settings = get_settings()
        self.server = Server(self.settings.mcp_server_name)
        self.memory_store = get_memory_store()
        self.skill_registry = get_skill_registry()
        self.tool_registry = get_tool_registry()
        self.prompt_assembler = PromptAssembler()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup MCP protocol handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List all available tools."""
            tools = []
            
            # Add all registered tools
            for spec in self.tool_registry.list_all():
                tools.append(Tool(
                    name=spec.name,
                    description=spec.description,
                    inputSchema=spec.parameters
                ))
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Execute a tool."""
            try:
                result = await self.tool_registry.execute(name, arguments)
                return [TextContent(type="text", text=str(result))]
            except Exception as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]
        
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """List available resources."""
            resources = []
            
            # Add system prompt as a resource
            resources.append(Resource(
                uri="myagent://system-prompt",
                name="Enhanced System Prompt",
                mimeType="text/markdown",
                description="System prompt with memory and skills context"
            ))
            
            # Add memory stats resource
            resources.append(Resource(
                uri="myagent://memory-stats",
                name="Memory Statistics",
                mimeType="application/json",
                description="Current memory store statistics"
            ))
            
            return resources
        
        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource."""
            if uri == "myagent://system-prompt":
                return self.prompt_assembler.assemble_system_prompt()
            
            elif uri == "myagent://memory-stats":
                stats = self.memory_store.get_stats()
                return json.dumps(stats, indent=2)
            
            else:
                raise ValueError(f"Unknown resource: {uri}")
    
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
    server = MyAgentMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
