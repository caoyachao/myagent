"""Command line interface for MyAgent."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from myagent.config import get_settings
from myagent.memory.store import MemoryStore
from myagent.skills.registry import SkillRegistry
from myagent.tools.registry import get_tool_registry

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """MyAgent - A local memory-enhanced agent layer for Kimi Code CLI."""
    pass


@main.command()
def init():
    """Initialize MyAgent configuration and directories."""
    settings = get_settings()
    
    console.print(Panel.fit(
        "[bold green]MyAgent initialized successfully![/]\n\n"
        f"Data directory: {settings.data_dir}\n"
        f"Config directory: {settings.config_dir}\n"
        f"Skills directory: {settings.skills_dir}",
        title="MyAgent",
        border_style="green"
    ))
    
    # Create example skill
    example_skill_dir = settings.skills_dir / "example"
    example_skill_dir.mkdir(exist_ok=True)
    
    example_skill_md = example_skill_dir / "SKILL.md"
    if not example_skill_md.exists():
        example_skill_md.write_text("""---
name: example
description: An example skill demonstrating the SKILL.md format
version: 1.0.0
author: user
tags: [example, demo]
tools: [hello]
---

# Example Skill

This is an example skill that demonstrates how to create skills for MyAgent.

## Capabilities

- Say hello to the user
- Demonstrate skill structure

## Usage

This skill is automatically loaded and its tools become available.
""")
        
        example_tools_py = example_skill_dir / "tools.py"
        example_tools_py.write_text("""from myagent.skills.registry import tool

@tool()
def hello(name: str = "World") -> str:
    \"\"\"Say hello to someone.\"\"\"
    return f"Hello, {name}! This is a skill tool."
""")
        
        console.print(f"\n[dim]Created example skill at: {example_skill_dir}[/dim]")


@main.command()
def serve():
    """Start the MCP server for Kimi Code CLI integration."""
    from myagent.mcp_server import main as mcp_main
    
    console.print(Panel.fit(
        "[bold blue]Starting MyAgent MCP Server...[/]\n\n"
        "This server provides memory and skill capabilities to Kimi Code CLI.\n"
        "Add the following to your Kimi CLI MCP config to use it.",
        title="MyAgent MCP Server",
        border_style="blue"
    ))
    
    # Print config snippet
    settings = get_settings()
    config_snippet = f'''{{
  "mcpServers": {{
    "myagent": {{
      "command": "python",
      "args": ["-m", "myagent.mcp_server"],
      "env": {{
        "MYAGENT_DATA_DIR": "{settings.data_dir}"
      }}
    }}
  }}
}}'''
    
    console.print("\n[bold]Configuration:[/]")
    console.print(f"[dim]{config_snippet}[/dim]")
    
    # Start server
    mcp_main()


@main.command()
def status():
    """Show MyAgent status and statistics."""
    settings = get_settings()
    
    # Get memory stats
    memory = MemoryStore()
    mem_stats = memory.get_stats()
    
    # Get skill registry
    skills = SkillRegistry()
    skill_list = skills.list_all()
    
    # Get tools
    tools = get_tool_registry().list_all()
    
    # Create tables
    console.print(Panel.fit(
        f"[bold]MyAgent Status[/]\n\n"
        f"Data directory: {settings.data_dir}\n"
        f"Config directory: {settings.config_dir}\n"
        f"Embedding model: {settings.embedding_model}",
        border_style="blue"
    ))
    
    # Memory stats
    mem_table = Table(title="Memory Statistics")
    mem_table.add_column("Metric", style="cyan")
    mem_table.add_column("Value", style="green")
    mem_table.add_row("Total Memories", str(mem_stats["total_memories"]))
    for mem_type, count in mem_stats["by_type"].items():
        mem_table.add_row(f"  {mem_type}", str(count))
    console.print(mem_table)
    
    # Skills
    skill_table = Table(title=f"Skills ({len(skill_list)})")
    skill_table.add_column("Name", style="cyan")
    skill_table.add_column("Description", style="green")
    skill_table.add_column("Tools", style="yellow")
    for skill in skill_list:
        skill_table.add_row(
            skill.name,
            skill.description[:50] + "..." if len(skill.description) > 50 else skill.description,
            ", ".join(skill.tools) if skill.tools else "-"
        )
    console.print(skill_table)
    
    # Tools
    tool_table = Table(title=f"Tools ({len(tools)})")
    tool_table.add_column("Name", style="cyan")
    tool_table.add_column("Description", style="green")
    tool_table.add_column("Source", style="yellow")
    for tool in tools:
        tool_table.add_row(tool.name, tool.description[:60], tool.source)
    console.print(tool_table)


@main.command()
@click.argument("content")
@click.option("--type", "memory_type", default="fact", 
              type=click.Choice(["fact", "preference", "event", "insight", "code"]))
@click.option("--tag", "tags", multiple=True, help="Tags for categorization")
def remember(content: str, memory_type: str, tags: tuple):
    """Save a memory directly from command line."""
    memory = MemoryStore()
    memory_id = memory.add(
        content=content,
        memory_type=memory_type,
        source="cli",
        tags=list(tags)
    )
    console.print(f"[green]Memory saved:[/] {content[:50]}...")
    console.print(f"[dim]ID: {memory_id}[/dim]")


@main.command()
@click.argument("query")
@click.option("--type", "memory_type", default=None)
@click.option("-n", "top_k", default=5)
def recall(query: str, memory_type: str, top_k: int):
    """Search memories from command line."""
    memory = MemoryStore()
    memories = memory.search(query, top_k=top_k, memory_type=memory_type)
    
    if not memories:
        console.print("[yellow]No memories found.[/]")
        return
    
    console.print(f"[bold]Found {len(memories)} memories:[/]")
    for i, mem in enumerate(memories, 1):
        console.print(f"\n[i]{i}.[/] [{mem.memory_type}] {mem.content}")
        if mem.tags:
            console.print(f"   [dim]Tags: {', '.join(mem.tags)}[/dim]")


@main.command()
def config():
    """Show configuration information."""
    settings = get_settings()
    
    console.print(Panel.fit(
        f"[bold]MyAgent Configuration[/]\n\n"
        f"Data Directory: {settings.data_dir}\n"
        f"Config Directory: {settings.config_dir}\n"
        f"Skills Directory: {settings.skills_dir}\n"
        f"Memory DB: {settings.memory_db_path}\n"
        f"Chroma Path: {settings.chroma_path}\n"
        f"Embedding Model: {settings.embedding_model}\n"
        f"Max Memories/Query: {settings.max_memories_per_query}\n"
        f"Auto-reload Skills: {settings.auto_reload_skills}",
        border_style="blue"
    ))


if __name__ == "__main__":
    main()
