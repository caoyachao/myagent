"""Command line interface for MyAgent 2.0."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from myagent.config import get_settings
from myagent.agent.manager import get_agent_manager
from myagent.agent.models import AgentCreateRequest
from myagent.memory.agent_store import AgentAwareMemoryStore
from myagent.agent.cleaner import AgentCleaner
from myagent.tools.skill_manager import SkillManager, get_skill_manager

console = Console()


@click.group()
@click.version_option(version="2.1.0")
def main():
    """MyAgent 2.0 - Multi-Agent memory-enhanced layer for Kimi Code CLI."""
    pass


@main.command()
def init():
    """Initialize MyAgent 2.0 configuration and directories."""
    settings = get_settings()
    agent_manager = get_agent_manager()
    
    # Check for migration from v1
    from myagent.migration import MigrationManager
    migration = MigrationManager()
    migration.check_and_migrate()
    
    current_agent = agent_manager.get_current_agent()
    
    console.print(Panel.fit(
        f"[bold green]MyAgent 2.0 initialized successfully![/]\n\n"
        f"Data directory: {settings.data_dir}\n"
        f"Config directory: {settings.config_dir}\n"
        f"Current agent: [cyan]{current_agent.name}[/]\n"
        f"Total agents: {len(agent_manager.list_agents())}",
        title="MyAgent 2.0",
        border_style="green"
    ))


@main.command()
def serve():
    """Start the MCP server for Kimi Code CLI integration."""
    from myagent.mcp_server import main as mcp_main
    
    agent_manager = get_agent_manager()
    current_agent = agent_manager.get_current_agent()
    
    console.print(Panel.fit(
        f"[bold blue]Starting MyAgent 2.0 MCP Server...[/]\n\n"
        f"Current agent: [cyan]{current_agent.name}[/]\n"
        f"This server provides multi-agent memory and skill capabilities.",
        title="MyAgent MCP Server",
        border_style="blue"
    ))
    
    # Print config snippet
    settings = get_settings()
    config_snippet = f"""{{
  \"mcpServers\": {{
    \"myagent\": {{
      \"command\": \"python\",
      \"args\": [\"-m\", \"myagent.mcp_server\"],
      \"env\": {{
        \"MYAGENT_DATA_DIR\": \"{settings.data_dir}\"
      }}
    }}
  }}
}}"""
    
    console.print("\n[bold]Configuration:[/]")
    console.print(f"[dim]{config_snippet}[/dim]")
    
    # Start server
    mcp_main()


@main.command()
def status():
    """Show MyAgent status and statistics."""
    settings = get_settings()
    agent_manager = get_agent_manager()
    current_agent = agent_manager.get_current_agent()
    
    # Get memory stats for current agent
    memory_store = AgentAwareMemoryStore(agent_manager)
    mem_stats = memory_store.get_stats()
    
    # Display current agent info
    console.print(Panel.fit(
        f"[bold cyan]【{current_agent.name}】[/]\n\n"
        f"ID: {current_agent.id}\n"
        f"Description: {current_agent.description or 'N/A'}\n"
        f"Personality: {current_agent.personality or 'N/A'}\n"
        f"Memories: {mem_stats['total_memories']}",
        title="Current Agent",
        border_style="cyan"
    ))
    
    # List all agents
    agents = agent_manager.list_agents()
    agent_table = Table(title=f"All Agents ({len(agents)})", box=box.ROUNDED)
    agent_table.add_column("Status", style="yellow", width=8)
    agent_table.add_column("Name", style="cyan")
    agent_table.add_column("ID", style="dim")
    agent_table.add_column("Memories", style="green", justify="right")
    agent_table.add_column("Skills", style="blue", justify="right")
    
    for agent in agents:
        status = "★ 当前" if agent.is_active else ""
        agent_table.add_row(
            status,
            agent.name + (" [主]" if agent.is_master else ""),
            agent.id,
            str(agent.memory_count),
            str(agent.skill_count)
        )
    
    console.print(agent_table)


# Agent management subcommand
@main.group()
def agent():
    """Manage agents (create, switch, delete, etc.)."""
    pass


@agent.command("create")
@click.argument("name")
@click.option("--description", "-d", default="", help="Agent description")
@click.option("--personality", "-p", default="", help="Personality traits")
@click.option("--system-prompt", "-s", default="", help="Additional system prompt")
@click.option("--inherit-shared-skills", is_flag=True, default=True, help="Inherit shared skills")
@click.option("--inherit-shared-tools", is_flag=True, default=True, help="Inherit shared tools")
@click.option("--inherit-master-memories", is_flag=True, default=False, help="Access master memories")
def create_agent(name, description, personality, system_prompt, 
                 inherit_shared_skills, inherit_shared_tools, inherit_master_memories):
    """Create a new agent."""
    agent_manager = get_agent_manager()
    
    request = AgentCreateRequest(
        name=name,
        description=description,
        personality=personality,
        system_prompt=system_prompt,
        inherit_shared_skills=inherit_shared_skills,
        inherit_shared_tools=inherit_shared_tools,
        inherit_master_memories=inherit_master_memories
    )
    
    try:
        new_agent = agent_manager.create_agent(request)
        console.print(Panel.fit(
            f"[bold green]✅ Agent '{new_agent.name}' created successfully![/]\n\n"
            f"ID: [cyan]{new_agent.id}[/]\n"
            f"Description: {new_agent.description or 'N/A'}\n"
            f"Personality: {new_agent.personality or 'N/A'}\n\n"
            f"Use [bold]myagent agent switch {new_agent.id}[/] to activate.",
            title="Agent Created",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")


@agent.command("list")
def list_agents():
    """List all agents."""
    agent_manager = get_agent_manager()
    agents = agent_manager.list_agents()
    
    if not agents:
        console.print("[yellow]No agents found.[/]")
        return
    
    table = Table(title=f"Agents ({len(agents)} total)", box=box.ROUNDED)
    table.add_column("Status", style="yellow", width=10)
    table.add_column("Name", style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Description", style="green")
    table.add_column("Memories", justify="right")
    
    for a in agents:
        status = "★ 当前" if a.is_active else ""
        table.add_row(
            status,
            a.name + (" [主]" if a.is_master else ""),
            a.id,
            a.description[:40] + "..." if len(a.description) > 40 else a.description,
            str(a.memory_count)
        )
    
    console.print(table)


@agent.command("switch")
@click.argument("agent_id")
def switch_agent(agent_id):
    """Switch to a different agent."""
    agent_manager = get_agent_manager()
    
    target = agent_manager.get_agent(agent_id)
    if not target:
        console.print(f"[bold red]Error:[/] Agent '{agent_id}' not found.")
        console.print("Use [bold]myagent agent list[/] to see available agents.")
        return
    
    try:
        agent_manager.switch_agent(agent_id)
        console.print(Panel.fit(
            f"[bold green]✅ Switched to '{target.name}'[/]\n\n"
            f"Description: {target.description or 'N/A'}\n"
            f"Personality: {target.personality or 'N/A'}",
            title="Agent Switched",
            border_style="green"
        ))
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")


@agent.command("delete")
@click.argument("agent_id")
@click.option("--force", is_flag=True, help="Skip confirmation")
def delete_agent(agent_id, force):
    """Delete an agent (cannot delete master)."""
    agent_manager = get_agent_manager()
    
    target = agent_manager.get_agent(agent_id)
    if not target:
        console.print(f"[bold red]Error:[/] Agent '{agent_id}' not found.")
        return
    
    if target.is_master:
        console.print("[bold red]Error:[/] Cannot delete the master agent.")
        return
    
    # Show what will be deleted
    console.print(Panel.fit(
        f"[bold yellow]即将删除智能体: {target.name}[/]\n\n"
        f"ID: {target.id}\n"
        f"记忆数据库: {target.memory_db_path}\n"
        f"向量存储: {target.chroma_path}\n"
        f"私有技能: {target.skills_dir}\n\n"
        f"[bold red]⚠️ 此操作不可恢复！[/]",
        title="Confirm Deletion",
        border_style="red"
    ))
    
    if not force:
        confirm = click.confirm("确认删除?")
        if not confirm:
            console.print("[yellow]已取消删除[/]")
            return
    
    try:
        # Delete from manager first
        agent_manager.delete_agent(agent_id)
        
        # Full cleanup
        cleaner = AgentCleaner(agent_manager)
        stats = cleaner.cleanup_agent_data(target)
        
        console.print(Panel.fit(
            f"[bold green]✅ Agent '{target.name}' deleted successfully![/]\n\n"
            f"Cleaned up:\n"
            f"  • Memory DB: {stats.memory_deleted and 'Yes' or 'No'} ({stats.memory_size_mb} MB)\n"
            f"  • Chroma files: {stats.chroma_files_deleted} files\n"
            f"  • Private skills: {stats.skills_deleted}\n"
            f"  • Config: {stats.config_deleted and 'Yes' or 'No'}",
            title="Deletion Complete",
            border_style="green"
        ))
        
        if stats.errors:
            console.print("[yellow]Warnings:[/]")
            for error in stats.errors:
                console.print(f"  • {error}")
                
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")


@agent.command("info")
def agent_info():
    """Show current agent information."""
    agent_manager = get_agent_manager()
    current = agent_manager.get_current_agent()
    
    # Get memory count
    memory_store = AgentAwareMemoryStore(agent_manager)
    mem_stats = memory_store.get_stats()
    
    info_text = f"""[bold cyan]【{current.name}】[/]

[b]ID:[/] {current.id}
[b]Description:[/] {current.description or 'N/A'}
[b]Personality:[/] {current.personality or 'N/A'}
[b]System Prompt:[/] {current.system_prompt or 'N/A'}

[bold]Statistics:[/]
  • Memories: {mem_stats['total_memories']}
  • Embedding model: {mem_stats['embedding_model']}

[bold]Inheritance:[/]
  • Shared skills: {'Yes' if current.inherit_shared_skills else 'No'}
  • Shared tools: {'Yes' if current.inherit_shared_tools else 'No'}
  • Master memories: {'Yes' if current.inherit_master_memories else 'No'}

[bold]Paths:[/]
  • Memory: {current.memory_db_path}
  • Chroma: {current.chroma_path}
  • Skills: {current.skills_dir}
"""
    
    if current.is_master:
        info_text += "\n[dim]This is the master agent.[/]"
    
    console.print(Panel.fit(info_text, title="Agent Info", border_style="cyan"))


# Memory commands
@main.command()
@click.argument("content")
@click.option("--type", "memory_type", default="fact",
              type=click.Choice(["fact", "preference", "event", "insight", "code"]))
@click.option("--tag", "tags", multiple=True, help="Tags for categorization")
@click.option("--share-with-master", is_flag=True, help="Also save to master agent")
def remember(content, memory_type, tags, share_with_master):
    """Save a memory to current agent."""
    agent_manager = get_agent_manager()
    memory_store = AgentAwareMemoryStore(agent_manager)
    
    memory_id = memory_store.add(
        content=content,
        memory_type=memory_type,
        tags=list(tags),
        share_with_master=share_with_master
    )
    
    current = agent_manager.get_current_agent()
    msg = f"[green]Memory saved to {current.name}[/] (ID: {memory_id})"
    if share_with_master and not current.is_master:
        msg += " [dim](also shared with master)[/]"
    console.print(msg)


@main.command()
@click.argument("query")
@click.option("--type", "memory_type", default=None)
@click.option("-n", "top_k", default=5)
@click.option("--include-master", is_flag=True, default=None, help="Include master memories")
def recall(query, memory_type, top_k, include_master):
    """Search memories from current agent."""
    agent_manager = get_agent_manager()
    memory_store = AgentAwareMemoryStore(agent_manager)
    
    memories = memory_store.search(
        query=query,
        top_k=top_k,
        memory_type=memory_type,
        include_master=include_master
    )
    
    if not memories:
        console.print("[yellow]No memories found.[/]")
        return
    
    current = agent_manager.get_current_agent()
    console.print(f"[bold]Memories from {current.name}:[/]\n")
    
    for i, mem in enumerate(memories, 1):
        console.print(f"{i}. [{mem.memory_type}] {mem.content}")
        if mem.tags:
            console.print(f"   [dim]Tags: {', '.join(mem.tags)}[/]")


@main.command()
def config():
    """Show configuration information."""
    settings = get_settings()
    agent_manager = get_agent_manager()
    current = agent_manager.get_current_agent()
    
    console.print(Panel.fit(
        f"[bold]MyAgent 2.0 Configuration[/]\n\n"
        f"Data Directory: {settings.data_dir}\n"
        f"Config Directory: {settings.config_dir}\n"
        f"Current Agent: {current.name} ({current.id})\n"
        f"Embedding Model: {settings.embedding_model}\n"
        f"Max Memories/Query: {settings.max_memories_per_query}\n"
        f"Auto-reload Skills: {settings.auto_reload_skills}",
        border_style="blue"
    ))


# Migration command
@main.command()
@click.option("--status", is_flag=True, help="Check migration status")
@click.option("--rollback", is_flag=True, help="Rollback migration")
def migrate(status, rollback):
    """Manage migration from MyAgent 1.0."""
    from myagent.migration import MigrationManager
    
    migration = MigrationManager()
    
    if status:
        if migration.is_migrated():
            console.print("[green]✓ Data has been migrated from v1.0[/]")
            info = migration.get_migration_info()
            console.print(f"Migrated at: {info.get('migrated_at', 'Unknown')}")
        else:
            console.print("[yellow]⚠ Data has not been migrated from v1.0[/]")
            if migration.detect_v1_data():
                console.print("[dim]v1.0 data detected. Run 'myagent init' to migrate.[/]")
    elif rollback:
        if click.confirm("Rollback to v1.0? This will remove v2.0 data."):
            migration.rollback()
            console.print("[green]Rollback completed.[/]")
    else:
        migration.check_and_migrate()


# Skill management commands
@main.group()
def skill():
    """Manage skills (install, uninstall, list, etc.)."""
    pass


@skill.command("install")
@click.argument("slug")
@click.option("--scope", "-s", type=click.Choice(["shared", "private"]), 
              default="shared", help="Installation scope")
@click.option("--version", "-v", default=None, help="Specific version to install")
def install_skill(slug, scope, version):
    """Install a skill from ClawHub."""
    skill_manager = get_skill_manager()
    
    console.print(f"[bold blue]Installing '{slug}'...[/]")
    
    with console.status("[bold green]Installing from ClawHub..."):
        result = skill_manager.install_from_clawhub(slug, scope, version)
    
    if not result.get("success"):
        console.print(f"[bold red]❌ Installation failed:[/] {result.get('error')}")
        if result.get("suggestion"):
            console.print(f"[yellow]💡 {result['suggestion']}[/]")
        return
    
    console.print(Panel.fit(
        f"[bold green]✅ Successfully installed '{result['skill_name']}'[/]\n\n"
        f"📦 Source: {result['slug']}\n"
        f"🔖 Version: {result['version']}\n"
        f"📍 Scope: [cyan]{result['scope']}[/]\n"
        f"📂 Location: {result['install_path']}",
        title="Skill Installed",
        border_style="green"
    ))
    
    if scope == "shared":
        console.print("[dim]💡 This skill is now available to all agents that inherit shared skills.[/]")
    else:
        console.print("[dim]💡 This skill is private to the current agent.[/]")


@skill.command("uninstall")
@click.argument("skill_name")
@click.option("--scope", "-s", type=click.Choice(["shared", "private"]), 
              default=None, help="Optional: specify scope if skill exists in both")
@click.option("--force", is_flag=True, help="Skip confirmation")
def uninstall_skill(skill_name, scope, force):
    """Uninstall a skill."""
    skill_manager = get_skill_manager()
    
    # First check where it's installed
    info = skill_manager.get_skill_info(skill_name)
    if not info.get("found"):
        console.print(f"[bold red]❌ Skill '{skill_name}' not found[/]")
        return
    
    if not force:
        confirm = click.confirm(f"Uninstall '{skill_name}' from {info['scope']}?")
        if not confirm:
            console.print("[yellow]Cancelled.[/]")
            return
    
    with console.status("[bold green]Uninstalling..."):
        result = skill_manager.uninstall(skill_name, scope)
    
    if not result.get("success"):
        console.print(f"[bold red]❌ Uninstall failed:[/] {result.get('error')}")
        return
    
    console.print(f"[bold green]✅ Uninstalled '{skill_name}' from {result['scope']}[/]")


@skill.command("list")
@click.option("--scope", "-s", type=click.Choice(["all", "shared", "private"]), 
              default="all", help="Filter by scope")
def list_skills(scope):
    """List all installed skills."""
    skill_manager = get_skill_manager()
    result = skill_manager.list_installed(scope)
    
    # Shared skills
    if result.get("shared"):
        console.print(f"\n[bold blue]🌐 Shared Skills ({len(result['shared'])})[/]")
        for skill in result["shared"]:
            console.print(f"  • [cyan]{skill['name']}[/] v{skill.get('version', '?')}")
            if skill.get("description"):
                desc = skill['description'][:50]
                if len(skill['description']) > 50:
                    desc += "..."
                console.print(f"    [dim]{desc}[/]")
    
    # Private skills
    if result.get("private"):
        console.print(f"\n[bold yellow]🔒 Private Skills ({len(result['private'])}) - {result['current_agent']}[/]")
        for skill in result["private"]:
            console.print(f"  • [cyan]{skill['name']}[/] v{skill.get('version', '?')}")
            if skill.get("description"):
                desc = skill['description'][:50]
                if len(skill['description']) > 50:
                    desc += "..."
                console.print(f"    [dim]{desc}[/]")
    
    if not result.get("shared") and not result.get("private"):
        console.print("[yellow]No installed skills found.[/]")
        console.print("[dim]Use 'myagent skill install <slug>' to install a skill.[/]")


@skill.command("info")
@click.argument("skill_name")
def skill_info(skill_name):
    """Show detailed information about a skill."""
    skill_manager = get_skill_manager()
    result = skill_manager.get_skill_info(skill_name)
    
    if not result.get("found"):
        console.print(f"[bold red]❌ Skill '{skill_name}' not found[/]")
        return
    
    info_text = f"""[bold cyan]📦 {result['name']}[/]

🔖 Version: {result.get('version', 'Unknown')}
📍 Scope: [cyan]{result['scope']}[/]
📂 Path: {result['path']}"""
    
    if result.get("author"):
        info_text += f"\n👤 Author: {result['author']}"
    
    if result.get("description"):
        info_text += f"\n\n📝 Description:\n{result['description']}"
    
    console.print(Panel.fit(info_text, title="Skill Info", border_style="cyan"))


@skill.command("search")
@click.argument("query")
@click.option("--limit", "-n", default=10, help="Maximum number of results")
def search_skills(query, limit):
    """Search for skills on ClawHub."""
    skill_manager = get_skill_manager()
    
    with console.status(f"[bold green]Searching for '{query}'..."):
        result = skill_manager.search_clawhub(query, limit)
    
    if not result.get("success"):
        console.print(f"[bold red]❌ Search failed:[/] {result.get('error')}")
        return
    
    console.print(f"\n[bold]🔍 Results for '{query}':[/]\n")
    console.print(result.get("results", "No results found."))


@skill.command("update")
@click.argument("skill_name")
def update_skill(skill_name):
    """Update a skill to the latest version."""
    skill_manager = get_skill_manager()
    
    # Check if skill exists
    info = skill_manager.get_skill_info(skill_name)
    if not info.get("found"):
        console.print(f"[bold red]❌ Skill '{skill_name}' not found[/]")
        return
    
    console.print(f"[bold blue]Updating '{skill_name}'...[/]")
    
    with console.status("[bold green]Updating..."):
        result = skill_manager.update_skill(skill_name)
    
    if not result.get("success"):
        console.print(f"[bold red]❌ Update failed:[/] {result.get('error')}")
        return
    
    console.print(f"[bold green]✅ Updated '{skill_name}' to latest version[/]")


# Archive commands
@main.group()
def archive():
    """Memory archiving and compression management."""
    pass


@archive.command("status")
def archive_status():
    """Show memory archive status."""
    from myagent.memory.archiver import MemoryArchiver
    
    agent_manager = get_agent_manager()
    current = agent_manager.get_current_agent()
    
    # Get active memory stats
    memory_store = AgentAwareMemoryStore(agent_manager)
    active_stats = memory_store.get_stats()
    
    # Get archive stats
    archiver = MemoryArchiver(
        agent_id=current.id,
        db_path=current.memory_db_path,
        chroma_path=current.chroma_path
    )
    archive_stats = archiver.get_archive_stats()
    
    # Analyze distribution
    distribution = archiver.analyze_distribution()
    
    console.print(Panel.fit(
        f"[bold cyan]【{current.name}】记忆归档状态[/]\n\n"
        f"[bold]活跃存储:[/]\n"
        f"  🔥 热数据 (Hot): {len(distribution.hot)}\n"
        f"  🌡️  温数据 (Warm): {len(distribution.warm)}\n"
        f"  ❄️  冷数据 (Cold): {len(distribution.cold)}\n"
        f"  总计: {distribution.total}\n\n"
        f"[bold]归档存储:[/]\n"
        f"  归档文件: {archive_stats['archive_count']}\n"
        f"  归档记忆: {archive_stats['total_memories']}\n"
        f"  占用空间: {archive_stats['total_size_mb']:.2f} MB",
        title="Archive Status",
        border_style="cyan"
    ))


@archive.command("analyze")
def archive_analyze():
    """Analyze memory distribution across tiers."""
    from myagent.memory.archiver import MemoryArchiver
    
    agent_manager = get_agent_manager()
    current = agent_manager.get_current_agent()
    
    archiver = MemoryArchiver(
        agent_id=current.id,
        db_path=current.memory_db_path,
        chroma_path=current.chroma_path
    )
    
    with console.status("[bold green]Analyzing memories..."):
        distribution = archiver.analyze_distribution()
    
    # Show hot memories
    if distribution.hot:
        console.print(f"\n[bold yellow]🔥 Hot Memories ({len(distribution.hot)}):[/]")
        for mem in distribution.hot[:5]:
            console.print(f"  • [{mem.memory_type}] {mem.content[:60]}...")
        if len(distribution.hot) > 5:
            console.print(f"  ... and {len(distribution.hot) - 5} more")
    
    # Show warm memories
    if distribution.warm:
        console.print(f"\n[bold blue]🌡️  Warm Memories ({len(distribution.warm)}):[/]")
        for mem in distribution.warm[:3]:
            console.print(f"  • [{mem.memory_type}] {mem.content[:60]}...")
        if len(distribution.warm) > 3:
            console.print(f"  ... and {len(distribution.warm) - 3} more")
    
    # Show cold memories
    if distribution.cold:
        console.print(f"\n[bold white]❄️  Cold Memories ({len(distribution.cold)}):[/]")
        console.print(f"  {len(distribution.cold)} memories ready for archiving")


@archive.command("run")
@click.option("--dry-run", is_flag=True, help="Simulate without making changes")
@click.option("--strategy", type=click.Choice(["summary", "merge", "dedup"]),
              help="Override compression strategy")
def archive_run(dry_run, strategy):
    """Run archiving maintenance."""
    from myagent.memory.archiver import MemoryArchiver
    from myagent.config import get_settings
    
    agent_manager = get_agent_manager()
    current = agent_manager.get_current_agent()
    
    if dry_run:
        console.print("[yellow]Dry run mode - no changes will be made[/]\n")
    
    # Override strategy if provided
    if strategy:
        settings = get_settings()
        original_strategy = settings.archive.compression_strategy
        settings.archive.compression_strategy = strategy
        console.print(f"[dim]Using strategy: {strategy}[/]")
    
    archiver = MemoryArchiver(
        agent_id=current.id,
        db_path=current.memory_db_path,
        chroma_path=current.chroma_path
    )
    
    with console.status("[bold green]Running maintenance..."):
        stats = archiver.run_maintenance()
    
    # Display results
    console.print(Panel.fit(
        f"[bold green]✅ Archive Maintenance Complete[/]\n\n"
        f"[bold]Distribution:[/]\n"
        f"  🔥 Hot: {stats['analysis']['hot']}\n"
        f"  🌡️  Warm: {stats['analysis']['warm']}\n"
        f"  ❄️  Cold: {stats['analysis']['cold']}\n\n"
        + (f"[bold]Compression:[/]\n"
           f"  Original: {stats['compression']['original_count']}\n"
           f"  Compressed: {stats['compression']['compressed_count']}\n"
           f"  Ratio: {stats['compression']['ratio']}\n"
           f"  Strategy: {stats['compression']['strategy']}\n\n"
           if stats['compression'] else "")
        + f"[bold]Cleanup:[/]\n"
        f"  Deleted from active: {stats['cleanup'].get('deleted_from_active', 0)}\n"
        f"  Archive files: {stats['archive_stats']['archive_count']}",
        title="Archive Results",
        border_style="green"
    ))


@archive.command("search")
@click.argument("query")
@click.option("-n", "top_k", default=5, help="Number of results")
def archive_search(query, top_k):
    """Search archived memories."""
    from myagent.memory.archiver import MemoryArchiver
    
    agent_manager = get_agent_manager()
    current = agent_manager.get_current_agent()
    
    archiver = MemoryArchiver(
        agent_id=current.id,
        db_path=current.memory_db_path,
        chroma_path=current.chroma_path
    )
    
    with console.status("[bold blue]Searching archives..."):
        results = archiver.search_archive(query, top_k=top_k)
    
    if not results:
        console.print("[yellow]No archived memories found.[/]")
        return
    
    console.print(f"[bold]Found {len(results)} archived memories:[/]\n")
    for i, mem in enumerate(results, 1):
        date_str = mem.created_at.strftime("%Y-%m-%d")
        console.print(f"{i}. [{date_str}] [{mem.memory_type}]")
        console.print(f"   {mem.content[:100]}...")
        if mem.metadata.get("compressed_from"):
            console.print(f"   [dim](compressed from {len(mem.metadata['compressed_from'])} memories)[/]")
        console.print()


@archive.command("config")
def archive_config():
    """Show archive configuration."""
    from myagent.config import get_settings
    
    config = get_settings().archive
    
    console.print(Panel.fit(
        f"[bold]Tier Thresholds:[/]\n"
        f"  Hot days: {config.hot_days}\n"
        f"  Warm days: {config.warm_days}\n\n"
        f"[bold]Activity Thresholds:[/]\n"
        f"  Hot activity: {config.hot_activity_threshold}\n"
        f"  Warm activity: {config.warm_activity_threshold}\n\n"
        f"[bold]Capacity Limits:[/]\n"
        f"  Max hot memories: {config.max_hot_memories}\n"
        f"  Max warm memories: {config.max_warm_memories}\n\n"
        f"[bold]Compression:[/]\n"
        f"  Strategy: {config.compression_strategy}\n"
        f"  Level: {config.compression_level}\n\n"
        f"[bold]Auto Archive:[/]\n"
        f"  Enabled: {'Yes' if config.auto_archive_enabled else 'No'}\n"
        f"  Interval: {config.auto_archive_interval_hours} hours",
        title="Archive Configuration",
        border_style="blue"
    ))


if __name__ == "__main__":
    main()