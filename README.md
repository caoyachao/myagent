# MyAgent

A local memory-enhanced agent layer for **Kimi Code CLI**.

## Features

- **Long-term Memory**: Persistent storage using SQLite + ChromaDB with semantic search
- **Skill System**: Dynamic skill loading with SKILL.md standard
- **Tool Registry**: Extensible tool system with built-in memory management
- **MCP Integration**: Native Model Context Protocol support for Kimi Code CLI
- **Local-First**: All data stored locally, no external API keys needed

## Installation

```bash
# Install dependencies
pip install -e .

# Or with uv
uv pip install -e .
```

## Quick Start

### 1. Initialize MyAgent

```bash
myagent init
```

This creates the necessary directories:
- Data: `~/.local/share/myagent/`
- Config: `~/.config/myagent/`
- Skills: `~/.config/myagent/skills/`

### 2. Configure Kimi Code CLI

Add MyAgent to your Kimi CLI MCP configuration (usually at `~/.kimi/mcp.json`):

```json
{
  "mcpServers": {
    "myagent": {
      "command": "python",
      "args": ["-m", "myagent.mcp_server"],
      "env": {
        "MYAGENT_DATA_DIR": "~/.local/share/myagent"
      }
    }
  }
}
```

### 3. Use MyAgent

Start Kimi Code CLI as usual:

```bash
kimi
```

MyAgent will automatically:
- Inject relevant memories into the context
- Provide available tools for memory management
- Load and activate skills based on context

## Available Tools

MyAgent provides these tools to Kimi Code CLI:

### Memory Tools

- `recall_memory(query, top_k=5, memory_type=None)` - Search memories
- `save_memory(content, memory_type="fact", tags=[])` - Save information
- `list_recent_memories(limit=10)` - List recent memories
- `forget_memory(memory_id)` - Delete a memory
- `get_memory_stats()` - Show memory statistics

### Skill Tools

- `list_skills()` - List available skills
- `get_skill_info(skill_name)` - Get skill details
- `reload_skills()` - Reload skills from disk
- `get_skills_directory()` - Show skills directory path

## Memory Types

- **fact**: Objective facts and knowledge
- **preference**: User preferences and habits
- **event**: Specific events and experiences
- **insight**: Insights and summaries
- **code**: Code snippets and technical solutions

## Creating Skills

Create a new skill by adding a directory under `~/.config/myagent/skills/`:

```
my_skill/
├── SKILL.md       # Skill definition
└── tools.py       # Tool implementations (optional)
```

### SKILL.md Format

```yaml
---
name: my_skill
description: What this skill does
version: 1.0.0
author: your_name
tags: [category1, category2]
tools: [tool_name1, tool_name2]
---

# Skill Documentation

Detailed description of the skill...
```

### tools.py Example

```python
from myagent.skills.registry import tool

@tool()
def my_tool(param: str) -> str:
    """Tool description."""
    return f"Result: {param}"
```

## CLI Commands

```bash
# Initialize
myagent init

# Start MCP server
myagent serve

# Show status
myagent status

# Save memory directly
myagent remember "Important information" --type fact --tag work

# Search memories
myagent recall "search query"

# Show configuration
myagent config
```

## Architecture

```
┌─────────────────┐
│   Kimi CLI      │
└────────┬────────┘
         │ MCP
         ▼
┌─────────────────┐
│   MyAgent       │
│  ┌───────────┐  │
│  │  Memory   │  │ ← SQLite + ChromaDB
│  │  System   │  │
│  ├───────────┤  │
│  │  Skill    │  │ ← SKILL.md files
│  │  Registry │  │
│  ├───────────┤  │
│  │  Tool     │  │ ← Built-in + Skills
│  │  Registry │  │
│  └───────────┘  │
└─────────────────┘
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
ruff check .
```

## License

MIT
