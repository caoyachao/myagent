"""Tool registry and execution."""

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolSpec:
    """Specification for a tool."""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable
    source: str = "builtin"  # 'builtin', 'skill', 'user'


class ToolRegistry:
    """Registry for managing tools."""
    
    def __init__(self):
        self._tools: Dict[str, ToolSpec] = {}
    
    def register(self, name: str, func: Callable, description: Optional[str] = None,
                 source: str = "builtin") -> ToolSpec:
        """Register a tool."""
        # Extract function signature for parameters
        sig = inspect.signature(func)
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue
            
            param_info = {"type": "string"}  # Default to string
            
            # Try to get type hint
            if param.annotation != inspect.Parameter.empty:
                if param.annotation == int:
                    param_info["type"] = "integer"
                elif param.annotation == float:
                    param_info["type"] = "number"
                elif param.annotation == bool:
                    param_info["type"] = "boolean"
                elif param.annotation == list or getattr(param.annotation, "__origin__", None) == list:
                    param_info["type"] = "array"
                elif param.annotation == dict:
                    param_info["type"] = "object"
            
            # Get default value
            if param.default != inspect.Parameter.empty:
                param_info["default"] = param.default
            else:
                parameters["required"].append(param_name)
            
            parameters["properties"][param_name] = param_info
        
        # Get description from docstring
        if description is None and func.__doc__:
            description = func.__doc__.strip().split("\n")[0]
        
        spec = ToolSpec(
            name=name,
            description=description or f"Tool: {name}",
            parameters=parameters,
            func=func,
            source=source
        )
        
        self._tools[name] = spec
        return spec
    
    def get(self, name: str) -> Optional[ToolSpec]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_all(self) -> List[ToolSpec]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def to_mcp_tools(self) -> List[Dict[str, Any]]:
        """Convert tools to MCP format."""
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.parameters
            }
            for spec in self._tools.values()
        ]
    
    async def execute(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool."""
        spec = self._tools.get(name)
        if spec is None:
            raise ValueError(f"Tool not found: {name}")
        
        func = spec.func
        
        # Check if async
        if asyncio.iscoroutinefunction(func):
            return await func(**arguments)
        else:
            return func(**arguments)


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(name: Optional[str] = None, description: Optional[str] = None):
    """Decorator to register a function as a tool."""
    def decorator(func):
        tool_name = name or func.__name__
        registry = get_tool_registry()
        registry.register(tool_name, func, description)
        return func
    return decorator
