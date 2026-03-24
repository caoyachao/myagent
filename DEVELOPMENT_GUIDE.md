# MyAgent MCP 架构设计与开发文档

## 目录

1. [系统概述](#系统概述)
2. [架构设计](#架构设计)
3. [核心模块详解](#核心模块详解)
4. [数据流与交互](#数据流与交互)
5. [工具接口说明](#工具接口说明)
6. [文件结构说明](#文件结构说明)
7. [开发指南](#开发指南)

---

## 系统概述

### 什么是 MyAgent MCP

MyAgent 是一个为 Kimi Code CLI 设计的**多智能体记忆增强层**，通过 MCP (Model Context Protocol) 协议与 Kimi CLI 集成，提供：

- **长期记忆**：持久化存储用户偏好、代码片段、技术决策等
- **多智能体支持**：创建多个具有不同人格和专长的智能体
- **技能系统**：动态加载技能模块，扩展功能
- **工具集成**：提供记忆管理、智能体管理等工具

### 核心特性

| 特性 | 说明 |
|------|------|
| 多智能体 | 支持创建多个独立智能体，各自拥有记忆和技能 |
| 记忆隔离 | 每个智能体有独立的 SQLite + ChromaDB 存储 |
| 继承系统 | 智能体可继承主智能体的共享技能和记忆 |
| 会话级切换 | `switch_agent` 只影响当前会话，支持多窗口独立运行 |
| 热重载 | 技能文件修改后自动重新加载 |

---

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Kimi Code CLI                                   │
│                         (MCP Client)                                    │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │ MCP Protocol
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     MyAgent MCP Server                                  │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                   AgentAwareMCPServer                            │   │
│  │  - session_agent_id: 会话级当前智能体                            │   │
│  │  - 所有工具调用都带【智能体名称】前缀                              │   │
│  │  - 动态根据当前智能体提供功能                                      │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                  │                                      │
│  ┌─────────────────┬─────────────┴─────────────┬──────────────────┐    │
│  │                 │                             │                  │    │
│  ▼                 ▼                             ▼                  │    │
│  ┌───────────┐ ┌───────────┐              ┌───────────┐           │    │
│  │   Tools   │ │ Resources │              │  Prompt   │           │    │
│  │  Handlers │ │  Handlers │              │ Assembler │           │    │
│  └─────┬─────┘ └───────────┘              └───────────┘           │    │
│        │                                                            │    │
└────────┼────────────────────────────────────────────────────────────┘    │
         │                                                                 │
         ▼                                                                 │
┌─────────────────────────────────────────────────────────────────────────┤
│                         核心系统层                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │AgentManager  │  │AgentAware    │  │AgentAware    │  │Memory      │  │
│  │              │  │MemoryStore   │  │SkillRegistry │  │Archiver    │  │
│  │- CRUD ops    │  │              │  │              │  │            │  │
│  │- Switching   │  │- SQLite      │  │- Shared      │  │- Compress  │  │
│  │- Persistence │  │- ChromaDB    │  │- Private     │  │- Archive   │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │
│         │                 │                  │                │        │
└─────────┼─────────────────┼──────────────────┼────────────────┼────────┘
          │                 │                  │                │
          ▼                 ▼                  ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         数据存储层                                       │
│  ~/.local/share/myagent/             ~/.config/myagent/                 │
│  ├── master/                         ├── shared_skills/                 │
│  │   ├── memories.db                 │   ├── code_assistant/            │
│  │   └── chroma/                     │   └── personal_assistant/        │
│  └── agents/                         └── agents/                         │
│      └── agent-{id}/                     └── agent-{id}/                 │
│          ├── memories.db                     ├── agent.json             │
│          └── chroma/                         └── skills/                 │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 核心模块详解

### 1. 配置管理 (config.py)

**文件**: `myagent/config.py`

**核心类**: `Settings` 和 `ArchiveConfig`

```python
class Settings(BaseSettings):
    """应用配置管理"""
    data_dir: Path          # ~/.local/share/myagent
    config_dir: Path        # ~/.config/myagent
    memory_db_path: Path    # SQLite 路径
    chroma_path: Path       # ChromaDB 路径
    embedding_model: str    # BAAI/bge-small-zh-v1.5
    archive: ArchiveConfig  # 归档配置

class ArchiveConfig:
    """记忆归档配置"""
    hot_days: int = 30          # Hot 层级天数
    warm_days: int = 90         # Warm 层级天数
    compression_strategy: str   # summary/merge/dedup
    compression_level: int = 6  # gzip 压缩级别
```

**关键方法**:
- `get_settings()` - 获取全局配置单例
- `get_archive_dir(agent_id)` - 获取 agent 归档目录

---

### 2. 智能体模型 (agent/models.py)

**文件**: `myagent/agent/models.py`

**核心类**:

#### Agent (智能体数据类)

```python
@dataclass
class Agent:
    id: str                           # 唯一标识 (UUID 前8位)
    name: str                         # 显示名称
    description: str                  # 描述
    personality: str                  # 人格特征
    system_prompt: str                # 系统提示词
    
    # 继承设置
    inherit_shared_skills: bool = True
    inherit_shared_tools: bool = True
    inherit_master_memories: bool = False
    
    # 存储路径 (自动派生)
    memory_db_path: Optional[Path]    # SQLite 数据库
    chroma_path: Optional[Path]       # 向量存储
    skills_dir: Optional[Path]        # 私有技能目录
    config_path: Optional[Path]       # 配置文件
    
    # 状态
    is_master: bool = False           # 是否主智能体
    is_active: bool = False           # 是否当前激活
    created_at: datetime
    updated_at: datetime
```

**路径派生规则**:
- Master: `~/.local/share/myagent/master/`
- Regular: `~/.local/share/myagent/agents/agent-{id}/`

#### 其他模型

```python
@dataclass
class AgentCreateRequest:
    """创建智能体请求"""
    name: str
    description: str = ""
    personality: str = ""
    system_prompt: str = ""
    inherit_shared_skills: bool = True
    inherit_shared_tools: bool = True
    inherit_master_memories: bool = False

@dataclass
class AgentSummary:
    """智能体摘要 (用于列表显示)"""
    id: str
    name: str
    description: str
    is_master: bool
    is_active: bool
    memory_count: int
    skill_count: int
```

---

### 3. 智能体管理器 (agent/manager.py)

**文件**: `myagent/agent/manager.py`

**核心类**: `AgentManager`

**设计模式**: 单例模式 (线程安全)

```python
class AgentManager:
    """管理所有智能体的 CRUD 和状态"""
    
    def __init__(self):
        self._agents: Dict[str, Agent] = {}      # 所有智能体缓存
        self._current_agent_id: Optional[str] = None  # 全局当前智能体
        self._lock = threading.RLock()            # 线程锁
        
    # ===== CRUD 操作 =====
    def create_agent(self, request: AgentCreateRequest) -> Agent
    def list_agents(self) -> List[AgentSummary]
    def get_agent(self, agent_id: str) -> Optional[Agent]
    def update_agent(self, agent_id: str, request: AgentUpdateRequest) -> Agent
    def delete_agent(self, agent_id: str) -> bool
    
    # ===== 智能体切换 =====
    def get_current_agent(self) -> Agent
    def switch_agent(self, agent_id: str) -> Agent
    
    # ===== 持久化 =====
    def _load_all_agents()          # 从磁盘加载
    def _save_current_agent_state() # 保存当前智能体到文件
```

**全局状态文件**: `~/.local/share/myagent/current_agent.json`

```json
{
  "current_agent_id": "87ea2669",
  "updated_at": "2026-03-23T10:30:00"
}
```

---

### 4. 记忆存储 (memory/agent_store.py)

**文件**: `myagent/memory/agent_store.py`

**核心类**: `AgentAwareMemoryStore`

**架构**: 双存储后端

```python
class AgentAwareMemoryStore:
    """智能体感知的记忆存储"""
    
    def __init__(self, agent_manager: AgentManager):
        self.agent_manager = agent_manager
        self._current_agent: Agent = None
        
        # SQLite 连接
        self.db_path: Path
        
        # ChromaDB 连接
        self.chroma_client: chromadb.Client
        self.collection: chromadb.Collection
        
    # ===== 核心操作 =====
    def add(self, content, memory_type="fact", ...) -> str:
        """添加记忆"""
        # 1. 生成 ID
        # 2. 存入 SQLite (元数据)
        # 3. 存入 Chroma (向量嵌入)
        
    def search(self, query, top_k=5, ...) -> List[Memory]:
        """语义搜索"""
        # 1. Chroma 向量搜索
        # 2. SQLite 获取完整记录
        # 3. 可选：包含 master 智能体记忆
        
    def get(self, memory_id: str) -> Optional[Memory]
    def delete(self, memory_id: str) -> bool
    def list_recent(self, limit=20) -> List[Memory]
    def get_stats(self) -> Dict
```

**数据表结构 (SQLite)**:

```sql
CREATE TABLE memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,      -- fact|preference|event|insight|code
    source TEXT NOT NULL,           -- 来源标识
    agent_id TEXT DEFAULT '{agent_id}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    tags TEXT,                      -- JSON 数组
    metadata TEXT                   -- JSON 对象
);

CREATE INDEX idx_type ON memories(memory_type);
CREATE INDEX idx_agent ON memories(agent_id);
CREATE INDEX idx_created ON memories(created_at);
```

---

### 5. 记忆归档 (memory/archiver.py)

**文件**: `myagent/memory/archiver.py`

**核心类**: `MemoryArchiver`

**功能**: 自动压缩和归档旧记忆，防止无限增长

```python
class MemoryArchiver:
    """记忆归档和压缩引擎"""
    
    # ===== 三层存储策略 =====
    # Hot:  最近 30 天 + 高活跃度
    # Warm: 30-90 天 + 中等活跃度  
    # Cold: 超过 90 天 + 低活跃度 (需要归档)
    
    def analyze_distribution(self) -> MemoryTierDistribution:
        """分析记忆分布"""
        
    def compress_memories(self, memories: List[Memory]) -> CompressionResult:
        """压缩记忆"""
        # 策略 1: summary - 按时间窗口生成摘要
        # 策略 2: merge - 合并相似记忆
        # 策略 3: dedup - 去重
        
    def run_maintenance(self) -> Dict:
        """运行完整维护"""
        # 1. 分析分布
        # 2. 压缩 Cold 记忆
        # 3. 写入归档文件
        # 4. 从活跃存储删除
```

**归档格式**: `archive_YYYYMMDD_HHMMSS.jsonl.gz`

---

### 6. 技能系统

#### 6.1 技能基类 (skills/base.py)

**文件**: `myagent/skills/base.py`

```python
@dataclass
class SkillInfo:
    """技能元数据"""
    name: str
    description: str
    version: str
    author: str
    tags: List[str]
    tools: List[str]

class Skill:
    """技能基类"""
    info: SkillInfo
    tools: Dict[str, Callable]
    
    def get_tool(self, name: str) -> Optional[Callable]
    def list_tools(self) -> List[str]

def parse_skill_md(content: str) -> SkillInfo:
    """解析 SKILL.md 文件"""
    # YAML frontmatter + Markdown
```

#### 6.2 技能注册表 (skills/registry.py)

**文件**: `myagent/skills/registry.py`

```python
class SkillRegistry:
    """技能发现和加载"""
    
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._load_all_skills()
        
    def _load_all_skills(self):
        """加载目录下所有技能"""
        # 1. 扫描 skills_dir 子目录
        # 2. 解析 SKILL.md
        # 3. 导入 tools.py
        # 4. 注册工具
        
    def list_all(self) -> List[SkillInfo]
    def get(self, name: str) -> Optional[Skill]
    def reload(self)  # 热重载
```

#### 6.3 智能体感知的技能注册表 (skills/agent_registry.py)

**文件**: `myagent/skills/agent_registry.py`

```python
class AgentAwareSkillRegistry:
    """组合共享技能和智能体私有技能"""
    
    def __init__(self, agent: Agent, agent_manager: AgentManager):
        # 共享技能 (所有智能体可用)
        self.shared_registry = SkillRegistry(shared_skills_dir)
        
        # 私有技能 (仅当前智能体)
        if agent.skills_dir:
            self.private_registry = SkillRegistry(agent.skills_dir)
    
    def list_all(self) -> List[SkillInfo]:
        """列出所有可用技能"""
        # 私有技能优先，去重
        skills = []
        if self.private_registry:
            skills.extend(self.private_registry.list_all())
        if self.agent.inherit_shared_skills:
            # 添加共享技能（排除已存在的）
            ...
        return skills
```

---

### 7. MCP 服务器 (mcp_server.py)

**文件**: `myagent/mcp_server.py`

**核心类**: `AgentAwareMCPServer`

**关键设计**: 会话级智能体切换

```python
class AgentAwareMCPServer:
    """增强的 MCP 服务器，支持多智能体"""
    
    def __init__(self):
        self.server = Server("myagent")
        self.agent_manager = get_agent_manager()
        
        # ===== 关键：会话级当前智能体 =====
        self.session_agent_id = "master"  # 每次启动默认 master
        
        self._refresh_agent_context()
        self._setup_handlers()
    
    def _refresh_agent_context(self):
        """刷新智能体上下文"""
        # 使用 session_agent_id 而非全局 current_agent
        self.current_agent = self.agent_manager.get_agent(self.session_agent_id)
        self.memory_store = AgentAwareMemoryStore(self.agent_manager)
        self.skill_registry = AgentAwareSkillRegistry(self.current_agent, ...)
        self.agent_tools = AgentTools(self.agent_manager)
        self.memory_tools = MemoryToolsV2(self.memory_store, self.current_agent)
    
    def _setup_handlers(self):
        """设置 MCP 协议处理器"""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """列出可用工具"""
            
        @self.server.call_tool()
        async def call_tool(name, arguments) -> List[TextContent]:
            """执行工具"""
            
        @self.server.list_resources()
        async def list_resources() -> List[Resource]:
            """列出资源"""
            
        @self.server.read_resource()
        async def read_resource(uri) -> str:
            """读取资源"""
```

---

### 8. 工具系统 (tools/agent_tools.py)

**文件**: `myagent/tools/agent_tools.py`

**核心类**: `AgentTools`

**完整工具列表**:

| 工具 | 功能 | 参数 |
|------|------|------|
| `list_agents` | 列出所有智能体 | - |
| `switch_agent` | 切换会话级智能体 | `agent_id` |
| `create_agent` | 创建新智能体 | `name`, `description`, `personality`, ... |
| `create_agent_from` | 克隆智能体 | `source_agent_id`, `new_name`, `copy_memories`, ... |
| `show_agent_info` | 显示智能体详情 | `agent_id` |
| `rename_agent` | 重命名智能体 | `agent_id`, `new_name` |
| `delete_agent` | 删除智能体 | `agent_id` |
| `get_current_info` | 获取当前智能体信息 | - |

#### create_agent_from 实现逻辑

```python
def create_agent_from(self, source_agent_id, new_name, ...):
    # 1. 获取源智能体
    source = self.agent_manager.get_agent(source_agent_id)
    
    # 2. 创建新智能体（复制配置）
    new_agent = self.agent_manager.create_agent(request)
    
    # 3. 复制记忆
    if copy_memories:
        self._copy_memories(source, new_agent)
        # SQLite 记录复制
        # Chroma 向量复制
    
    # 4. 复制技能
    if copy_skills:
        self._copy_skills(source, new_agent)
        # 复制 skills/ 目录
    
    return success_message
```

---

## 数据流与交互

### 1. 启动流程

```
1. Kimi CLI 启动
   │
   ▼
2. 加载 MCP 配置 (~/.kimi/mcp.json)
   │
   ▼
3. 启动 MyAgent MCP Server
   │
   ├── 初始化 Settings (读取配置)
   ├── 初始化 AgentManager
   │   ├── 加载 master 智能体
   │   ├── 加载所有普通智能体
   │   └── 设置 session_agent_id = "master"
   │
   └── 初始化 AgentAwareMCPServer
       ├── 创建 MemoryStore
       ├── 创建 SkillRegistry
       └── 注册工具处理器
   │
   ▼
4. 等待 MCP 请求
```

### 2. 工具调用流程

```
用户输入: "帮我搜索关于 Python 的记忆"
   │
   ▼
Kimi CLI 解析意图
   │
   ▼
调用 recall_memory 工具
   │
   ▼
MyAgent MCP Server
   │
   ├── _refresh_agent_context()
   │   └── 使用 session_agent_id 获取当前智能体
   │
   ├── memory_tools.recall(query="Python")
   │   │
   │   ├── ChromaDB 向量搜索
   │   ├── SQLite 获取完整记录
   │   └── 可选：搜索 master 智能体记忆
   │
   └── _wrap_with_agent(result)
       └── 添加 【智能体名称】前缀
   │
   ▼
返回结果给 Kimi CLI
```

### 3. 智能体切换流程

```
用户: "切换到编程助手"
   │
   ▼
调用 switch_agent(agent_id="xxx")
   │
   ▼
AgentAwareMCPServer._switch_agent_session()
   │
   ├── 验证 agent_id 存在
   ├── self.session_agent_id = agent_id  (仅会话级)
   ├── _refresh_agent_context()  (刷新内存、技能等)
   │
   └── 返回切换成功信息
   │
   ▼
后续工具调用使用新的 session_agent_id
```

---

## 工具接口说明

### 记忆管理工具 (MemoryToolsV2)

```python
class MemoryToolsV2:
    def recall(self, query: str, top_k: int = 5, 
               memory_type: str = None, 
               include_master: bool = None) -> str
    
    def save(self, content: str, memory_type: str = "fact",
             tags: List[str] = None, 
             share_with_master: bool = False) -> str
    
    def list_recent(self, limit: int = 10, 
                    memory_type: str = None) -> str
    
    def forget(self, memory_id: str) -> str
    
    def get_stats(self) -> str
```

### 智能体管理工具 (AgentTools)

```python
class AgentTools:
    # 基础 CRUD
    def list_agents(self) -> str
    def create_agent(self, name: str, ...) -> str
    def delete_agent(self, agent_id: str) -> str
    
    # 增强功能
    def create_agent_from(self, source_agent_id: str, 
                          new_name: str, 
                          copy_memories: bool = True,
                          copy_skills: bool = True,
                          copy_personality: bool = True) -> str
    
    def show_agent_info(self, agent_id: str) -> str
    
    def rename_agent(self, agent_id: str, 
                     new_name: str) -> str
```

---

## 文件结构说明

### 项目目录结构

```
myagent/                          # 主包
├── __init__.py                   # 包入口
├── __main__.py                   # python -m myagent 入口
│
├── config.py                     # 配置管理
│   ├── ArchiveConfig             # 归档配置
│   └── Settings                  # 全局配置
│
├── cli.py                        # 命令行界面 (Click)
│   ├── init()                    # 初始化
│   ├── serve()                   # 启动 MCP 服务器
│   ├── status()                  # 查看状态
│   └── ...                       # 其他命令
│
├── mcp_server.py                 # MCP 服务器实现 ⭐核心
│   └── AgentAwareMCPServer       # 增强 MCP 服务
│
├── agent/                        # 智能体模块
│   ├── __init__.py
│   ├── models.py                 # Agent 数据模型
│   │   ├── Agent                 # 智能体类
│   │   ├── AgentCreateRequest    # 创建请求
│   │   └── AgentSummary          # 智能体摘要
│   ├── manager.py                # AgentManager 智能体管理
│   └── cleaner.py                # AgentCleaner 清理工具
│
├── memory/                       # 记忆系统
│   ├── __init__.py
│   ├── store.py                  # Memory 数据类
│   ├── agent_store.py            # AgentAwareMemoryStore ⭐核心
│   └── archiver.py               # MemoryArchiver 归档引擎
│
├── skills/                       # 技能系统
│   ├── __init__.py
│   ├── base.py                   # Skill 基类和解析
│   ├── registry.py               # SkillRegistry 技能注册表
│   └── agent_registry.py         # AgentAwareSkillRegistry ⭐核心
│
├── tools/                        # 工具系统
│   ├── __init__.py
│   ├── registry.py               # ToolRegistry 工具注册
│   ├── agent_tools.py            # AgentTools 智能体管理 ⭐核心
│   ├── memory_tools_v2.py        # MemoryToolsV2 记忆管理 ⭐核心
│   └── skill_tools.py            # 技能相关工具
│
├── prompt/                       # 提示词组装
│   ├── __init__.py
│   └── assembler.py              # PromptAssembler
│
├── core/                         # 核心功能（预留）
│   └── __init__.py
│
└── migration.py                  # v1.0 → v2.0 迁移工具

skills/                           # 示例技能目录
├── code_assistant/               # 代码助手技能
│   ├── SKILL.md
│   └── tools.py
└── personal_assistant/           # 个人助手技能
    ├── SKILL.md
    └── tools.py

tests/
├── test_basic.py                 # 基础测试
└── test_archive.py               # 归档测试

data/                             # 运行时数据（Git 忽略）
```

### 数据存储结构

```
~/.local/share/myagent/           # 数据目录
├── master/                       # 主智能体数据
│   ├── agent.json               # 主智能体配置
│   ├── memories.db              # SQLite 数据库
│   └── chroma/                  # ChromaDB 向量存储
│
├── agents/                       # 其他智能体
│   └── agent-{uuid}/
│       ├── memories.db
│       └── chroma/
│
└── current_agent.json           # 全局当前智能体状态

~/.config/myagent/                # 配置目录
├── shared_skills/               # 共享技能
│   ├── code_assistant/
│   └── personal_assistant/
│
├── agents/                      # 智能体配置
│   └── agent-{uuid}/
│       ├── agent.json
│       └── skills/              # 私有技能
│
└── master/
    └── agent.json
```

---

## 开发指南

### 1. 添加新工具

在 `myagent/tools/agent_tools.py` 中添加:

```python
def my_new_tool(self, param1: str, param2: int = 10) -> str:
    """工具描述"""
    # 实现逻辑
    return "结果"
```

在 `myagent/mcp_server.py` 中注册:

```python
# 1. 在 _get_agent_management_tools() 中添加 Tool 定义
Tool(
    name="my_new_tool",
    description="工具描述",
    inputSchema={
        "type": "object",
        "properties": {
            "param1": {"type": "string"},
            "param2": {"type": "integer", "default": 10}
        },
        "required": ["param1"]
    }
)

# 2. 在 _execute_tool() 中添加处理
elif name == "my_new_tool":
    return self.agent_tools.my_new_tool(**arguments)
```

### 2. 添加新技能

创建目录 `~/.config/myagent/shared_skills/my_skill/`:

**SKILL.md**:
```markdown
---
name: my_skill
description: 我的技能
version: 1.0.0
tools:
  - my_tool
---

# 使用说明
...
```

**tools.py**:
```python
def my_tool(param: str) -> str:
    """工具描述"""
    return f"结果: {param}"
```

### 3. 调试技巧

```bash
# 查看日志
myagent status

# 直接启动 MCP 服务器查看输出
myagent serve

# 运行测试
python -m pytest test_basic.py -v

# 查看数据
sqlite3 ~/.local/share/myagent/master/memories.db "SELECT * FROM memories;"
```

---

## 附录

### 记忆类型说明

| 类型 | 用途 | 权重 |
|------|------|------|
| `fact` | 客观事实 | 0.9 |
| `preference` | 用户偏好 | 1.5 |
| `event` | 特定事件 | 1.0 |
| `insight` | 洞察总结 | 1.3 |
| `code` | 代码片段 | 1.2 |

### 配置文件示例

**mcp.json** (~/.kimi/mcp.json):
```json
{
  "mcpServers": {
    "myagent": {
      "command": "python3",
      "args": ["-m", "myagent.mcp_server"],
      "env": {
        "MYAGENT_DATA_DIR": "~/.local/share/myagent",
        "MYAGENT_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

*文档版本: 2.0*
*最后更新: 2026-03-24*
