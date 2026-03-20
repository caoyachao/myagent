# MyAgent 架构设计

## 核心设计思想

MyAgent 是一个**前置增强层**，它在 Kimi Code CLI 调用 Moonshot API 之前，注入本地记忆、技能和工具上下文。

```
传统方式：                    MyAgent 方式：
┌──────────┐                ┌──────────┐
│  用户    │                │  用户    │
└────┬─────┘                └────┬─────┘
     │                           │
     ▼                           ▼
┌──────────┐                ┌──────────┐
│Kimi CLI  │                │ MyAgent  │  ← 注入记忆和技能
│          │                │ MCP 层   │
└────┬─────┘                └────┬─────┘
     │                           │
     ▼                           ▼
┌──────────┐                ┌──────────┐
│Moonshot  │                │Kimi CLI  │
│  API     │                │          │
└──────────┘                └────┬─────┘
                                 │
                                 ▼
                           ┌──────────┐
                           │Moonshot  │
                           │  API     │
                           └──────────┘
```

## 系统架构

### 1. 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                        用户输入                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     MyAgent MCP Server                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Tool        │  │ Resource    │  │ Prompt Enhancement  │ │
│  │ Handlers    │  │ Handlers    │  │                     │ │
│  │             │  │             │  │ • Recall memories   │ │
│  │ • Memory    │  │ • System    │  │ • Load skills       │ │
│  │ • Skills    │  │   Prompt    │  │ • Inject tools      │ │
│  │ • Custom    │  │ • Stats     │  │                     │ │
│  └──────┬──────┘  └─────────────┘  └─────────────────────┘ │
└─────────┼───────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                      核心系统层                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ MemoryStore  │  │ SkillRegistry│  │ ToolRegistry     │  │
│  │              │  │              │  │                  │  │
│  │ SQLite       │  │ SKILL.md     │  │ Built-in         │  │
│  │ ChromaDB     │  │ Hot-reload   │  │ Skills           │  │
│  │ Embeddings   │  │ Discovery    │  │ User-defined     │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2. 记忆系统架构

```
┌─────────────────────────────────────────────────┐
│                 MemoryStore                      │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐      ┌──────────────────┐     │
│  │   SQLite     │      │    ChromaDB      │     │
│  │              │      │                  │     │
│  │ • Metadata   │      │ • Vectors        │     │
│  │ • Timestamps │      │ • Embeddings     │     │
│  │ • Tags       │◄────►│ • Semantic Index │     │
│  │ • Stats      │      │ • Similarity     │     │
│  └──────────────┘      └──────────────────┘     │
│                                                  │
│  存储格式：                                       │
│  - ID: hash(content + timestamp)                 │
│  - Type: fact|preference|event|insight|code      │
│  - Embedding: sentence-transformers              │
└─────────────────────────────────────────────────┘
```

### 3. 技能系统架构

```
┌─────────────────────────────────────────────────┐
│               SkillRegistry                      │
├─────────────────────────────────────────────────┤
│                                                  │
│   ~/.config/myagent/skills/                     │
│   ├── code_assistant/                           │
│   │   ├── SKILL.md    ← YAML frontmatter        │
│   │   └── tools.py    ← Tool implementations    │
│   ├── personal_assistant/                       │
│   └── ...                                       │
│                                                  │
│   加载流程：                                      │
│   1. Scan directory                             │
│   2. Parse SKILL.md                             │
│   3. Import tools.py                            │
│   4. Register tools                             │
│   5. Watch for changes                          │
└─────────────────────────────────────────────────┘
```

### 4. 工具系统架构

```
┌─────────────────────────────────────────────────┐
│               ToolRegistry                       │
├─────────────────────────────────────────────────┤
│                                                  │
│  内置工具 (Builtin)                              │
│  ├── recall_memory()        → MemoryStore       │
│  ├── save_memory()          → MemoryStore       │
│  ├── list_skills()          → SkillRegistry     │
│  └── ...                                        │
│                                                  │
│  技能工具 (From Skills)                          │
│  ├── code_assistant.save_snippet()              │
│  ├── code_assistant.search_snippets()           │
│  └── personal_assistant.save_preference()       │
│                                                  │
│  注册方式：                                       │
│  • @register_tool() 装饰器                       │
│  • @tool() in skills                            │
│  • Auto-discovery                               │
└─────────────────────────────────────────────────┘
```

### 5. 提示词组装流程

```
┌─────────────────────────────────────────────────┐
│            PromptAssembler                       │
├─────────────────────────────────────────────────┤
│                                                  │
│  Input: user_query                               │
│                                                  │
│  1. Get Base Prompt                              │
│     └── System role & principles                │
│                                                  │
│  2. Get User Profile                             │
│     └── Search preferences                      │
│                                                  │
│  3. Get Relevant Memories                        │
│     └── Semantic search                         │
│     └── Update access stats                     │
│                                                  │
│  4. Get Available Skills                         │
│     └── List all loaded skills                  │
│                                                  │
│  5. Get Available Tools                          │
│     └── List all registered tools               │
│                                                  │
│  Output: Enhanced System Prompt                  │
└─────────────────────────────────────────────────┘
```

## 关键技术决策

### 1. 为什么用 MCP？

- **标准化**: MCP 是 Model Context Protocol，Kimi CLI 原生支持
- **无侵入**: 不需要修改 Kimi CLI 代码
- **双向通信**: 支持工具调用和资源读取

### 2. 为什么 SQLite + ChromaDB？

- **SQLite**: 轻量、可靠、零配置，存储元数据
- **ChromaDB**: 本地向量库，支持语义搜索
- **组合**: 关系型 + 向量 = 完整解决方案

### 3. 为什么 SKILL.md 标准？

- **兼容性**: 与 Claude Code、Cursor 等工具的技能格式一致
- **可读性**: Markdown + YAML，人类友好
- **可移植**: 易于分享和复用

### 4. 为什么本地嵌入模型？

- **隐私**: 数据不上传
- **成本**: 无需 API 费用
- **速度**: 本地推理快
- **离线**: 无需网络连接

## 扩展点

### 添加新的内置工具

```python
# myagent/tools/my_tools.py
from myagent.tools.registry import register_tool

@register_tool(name="my_tool", description="Does something")
def my_tool(param: str) -> str:
    return f"Result: {param}"
```

### 添加新的记忆类型

```python
# 在 MemoryType 中添加新类型
# 自动支持，无需其他修改
memory_store.add(content, memory_type="new_type")
```

### 添加新的向量后端

```python
# 替换 MemoryStore._init_chroma()
# 保持相同接口即可
```

## 性能考虑

| 组件 | 性能特征 | 优化策略 |
|------|----------|----------|
| SQLite | < 10ms 查询 | 索引优化 |
| Chroma | ~50ms 搜索 | 缓存嵌入 |
| 技能加载 | 启动时一次 | 热重载 |
| 提示词组装 | ~100ms | 异步缓存 |

## 安全考虑

1. **本地数据**: 所有数据存储在本地文件系统
2. **无外部调用**: 不调用外部 API（除非配置）
3. **代码执行**: 技能代码在本地执行，需谨慎
4. **配置隔离**: 支持项目级和用户级配置

## 未来扩展

- [ ] 知识图谱集成
- [ ] 多 Agent 协作
- [ ] Web UI 管理界面
- [ ] 记忆压缩和归档
- [ ] 云同步选项
- [ ] 更多技能市场
