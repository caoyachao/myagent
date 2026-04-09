# MyAgent 2.1.0

A **multi-agent**, memory-enhanced layer for **CLI** with unified **Skill Management**.

## What's New in 2.1.0

- **📦 Unified Skill Management**: Install skills via MCP tools or CLI with shared/private scope
- **🌐 Cross-CLI Consistency**: Skills installed via MyAgent are available across all MCP-enabled CLIs
- **🎯 Smart Installation**: LLM automatically uses MyAgent's install system instead of direct clawhub

## What's New in 2.0

- **🎭 Multi-Agent Support**: Create multiple agents with different personalities
- **🔒 Agent Isolation**: Each agent has its own memory and private skills  
- **🔗 Inheritance System**: Share skills and memories between agents
- **👑 Master Agent**: Default agent that holds shared resources
- **🔄 Easy Switching**: Switch between agents seamlessly
- **📛 Identity Display**: Every response shows which agent is speaking

## Features

- **Long-term Memory**: Persistent storage using SQLite + ChromaDB with semantic search
- **Skill System**: Dynamic skill loading with SKILL.md standard (shared + private)
- **Unified Skill Management**: Install from ClawHub with `--shared` (all agents) or `--private` (current agent)
- **Multi-Agent**: Create specialized agents for different tasks
- **MCP Integration**: Native Model Context Protocol support for Kimi Code CLI
- **Cross-CLI Compatible**: Skills work across Kimi, Claude, and other MCP-enabled CLIs
- **Local-First**: All data stored locally, no external API keys needed

## Installation

```bash
cd /Users/yachaocao/Projects/MyAgent
pip install -e .
```

## Quick Start

### 1. Initialize

```bash
myagent init
```

This will:
- Create necessary directories
- Set up the **Master Agent**
- Automatically migrate data from v1.0 if detected

### 2. Configure Kimi Code CLI

Add to `~/.kimi/mcp.json`:

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

### 3. Create Your First Agent

```bash
myagent agent create "编程助手" \
  --description "专业的代码审查和开发助手" \
  --personality "严谨、高效、注重代码质量" \
  --system-prompt "你是一位资深软件工程师，擅长代码审查和架构设计。"
```

### 4. Start Using

```bash
kimi
```

Then in conversation:
```
用户：切换到编程助手
Kimi：> 调用 switch_agent

【编程助手】已切换到编程助手。你好！我是你的编程助手...
```

## CLI Commands

### Agent Management

```bash
# List all agents
myagent agent list

# Create a new agent
myagent agent create "写作助手" \
  --description "创意写作专家" \
  --personality "富有创意、善于表达"

# Switch to an agent
myagent agent switch <agent-id>

# Show current agent info
myagent agent info

# Delete an agent (cleans up all data)
myagent agent delete <agent-id>
```

### Memory Commands

```bash
# Save memory to current agent
myagent remember "我喜欢用 FastAPI" --type preference --tag python

# Search memories
myagent recall "Python 框架"

# Include master memories in search
myagent recall "项目经验" --include-master
```

### Skill Management (New in 2.1.0)

```bash
# Install a skill from ClawHub (shared - all agents can use)
myagent skill install think-plan --scope shared

# Install a skill for current agent only (private)
myagent skill install code-reviewer --scope private

# List all installed skills
myagent skill list

# Show skill details
myagent skill info think-plan

# Search for skills on ClawHub
myagent skill search "code review"

# Update a skill to latest version
myagent skill update think-plan

# Uninstall a skill
myagent skill uninstall think-plan
```

### System Commands

```bash
# Show status of current agent
myagent status

# Show configuration
myagent config

# Start MCP server manually
myagent serve
```

## Using in Kimi CLI

### Available Tools

**Agent Management:**
- `list_agents()` - List all available agents
- `switch_agent(agent_id)` - Switch to a different agent
- `create_agent(name, ...)` - Create a new agent
- `delete_agent(agent_id)` - Delete an agent
- `get_current_agent_info()` - Get current agent info

**Memory Tools:**
- `recall_memory(query, top_k=5)` - Search agent's memories
- `save_memory(content, type="fact")` - Save to agent's memory
- `list_recent_memories(limit=10)` - List recent memories
- `forget_memory(id)` - Delete a memory
- `get_memory_stats()` - Show memory statistics

**Skill Tools:**
- `install_skill(slug, scope)` - ⚠️ **PRIORITY**: Install skill from ClawHub (use this first!)
- `uninstall_skill(skill_name)` - Uninstall a skill
- `list_skills(scope)` - List installed skills with their scope
- `search_skills(query)` - Search for skills on ClawHub
- `get_skill_info(skill_name)` - Get skill details
- `update_skill(skill_name)` - Update to latest version
- `reload_skills()` - Reload skills from disk

### Example Conversation

```
用户：帮我创建一个新的智能体，叫"心理咨询师"，性格要温柔、善解人意

Kimi：> 调用 create_agent
      name: 心理咨询师
      personality: 温柔、善解人意、善于倾听

【默认助手】✅ Agent '心理咨询师' created successfully!
   ID: a1b2c3d4

用户：切换到心理咨询师

Kimi：> 调用 switch_agent
      agent_id: a1b2c3d4

【心理咨询师】已切换到心理咨询师。你好！这里是一个安全的空间，
你可以畅所欲言...

用户：我最近工作压力很大...

【心理咨询师】我理解你的感受。工作压力是现代人常见的问题...
```

### Skill Management Example

```
用户：我想安装一个代码审查的 skill

Kimi：> 调用 search_skills
      query: "code review"

【编程助手】找到以下代码审查相关的 Skill：
1. code-reviewer - 专业的代码审查助手
2. pr-assistant - PR 审查和生成工具

请选择要安装的 Skill，或告诉我具体的 slug。

用户：安装第一个，给当前 agent 私有使用

Kimi：> 调用 install_skill
      slug: code-reviewer
      scope: private

【编程助手】✅ Successfully installed 'code-reviewer'
   Scope: private (仅当前 Agent 可用)
   Location: ~/Library/.../agents/agent-xxx/skills/code-reviewer/

用户：这个 skill 在其他 agent 也能用吗？

【编程助手】不能，这个 skill 是私有的，只有当前 Agent (编程助手) 可以使用。
如果你想让所有 agent 都能用，可以重新安装为 shared 范围。
```

## Agent Identity Display

Every response automatically shows which agent is speaking:

```
【编程助手】已找到相关代码片段...
【写作助手】这是根据你的要求写的文章...
【默认助手】有什么可以帮你的吗？
【心理咨询师】我理解你的感受...
```

## Data Structure

```
~/.local/share/myagent/
├── master/                    # Master agent (shared resources)
│   ├── memories.db           # Master memories
│   └── chroma/               # Master vector store
└── agents/                    # Other agents
    └── agent-{uuid}/
        ├── memories.db       # Agent's private memories
        └── chroma/           # Agent's vector store

~/.config/myagent/
├── shared_skills/            # Shared skills (all agents can use)
│   ├── code_assistant/
│   └── personal_assistant/
└── agents/
    └── agent-{uuid}/
        └── skills/           # Private skills (only this agent)
```

## Migration from 1.0

Data from MyAgent 1.0 is **automatically migrated** when you run `myagent init`:

| v1.0 | → | v2.0 (Master Agent) |
|------|---|---------------------|
| `memories.db` | → | `master/memories.db` |
| `chroma/` | → | `master/chroma/` |
| `skills/` | → | `shared_skills/` |

A backup is created at `~/.local/share/myagent/backup_v1.0_*`

### Check Migration Status

```bash
myagent migrate --status
```

### Rollback (if needed)

```bash
myagent migrate --rollback
```

## Skill Management

### Installing from ClawHub (Recommended)

MyAgent 2.1.0 provides unified skill installation that works across all MCP-enabled CLIs:

```bash
# Install as shared skill (all agents can use)
myagent skill install caoyachao/think-plan --scope shared

# Install as private skill (only current agent)
myagent skill install caoyachao/think-plan --scope private
```

**Why use MyAgent instead of `clawhub install` directly?**
- ✅ Skills are linked to your Agent identity
- ✅ Works consistently across Kimi, Claude, and other MCP CLIs
- ✅ Easy management (list, update, uninstall)
- ✅ Clear scope control (shared vs private)

### Creating Custom Skills

### Shared Skills (All Agents)

Create in `~/.config/myagent/shared_skills/`:

```
shared_skills/
└── my_skill/
    ├── SKILL.md
    └── tools.py
```

### Private Skills (Single Agent)

Create in `~/.config/myagent/agents/agent-{uuid}/skills/`:

```
agents/agent-{uuid}/skills/
└── private_skill/
    ├── SKILL.md
    └── tools.py
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

Detailed description...
```

### tools.py Example

```python
from myagent.skills.registry import tool

@tool()
def my_tool(param: str) -> str:
    """Tool description."""
    return f"Result: {param}"
```

## Memory Types

- **fact**: Objective facts and knowledge
- **preference**: User preferences and habits
- **event**: Specific events and experiences
- **insight**: Insights and summaries
- **code**: Code snippets and technical solutions

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│   Kimi CLI      │     │  Claude Code    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │ MCP
                     ▼
        ┌────────────────────────────┐
        │      MyAgent 2.1.0         │
        │  ┌──────────────────────┐  │
        │  │   Skill Manager      │  │  ← NEW in 2.1.0
        │  │  (ClawHub install)   │  │
        │  └──────────────────────┘  │
        │  ┌──────────────────────┐  │
        │  │   Agent Manager      │  │
        │  │  ┌────┐ ┌────┐      │  │
        │  │  │ A1 │ │ A2 │ ...  │  │
        │  │  └──┬─┘ └──┬─┘      │  │
        │  └─────┼──────┼────────┘  │
        │        │      │            │
        │  ┌─────▼──────▼────────┐   │
        │  │ AgentAwareMemory    │   │
        │  │ AgentAwareSkills    │   │
        │  └─────────────────────┘   │
        └────────────────────────────┘
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
