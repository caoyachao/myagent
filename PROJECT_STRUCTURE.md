# MyAgent 项目结构

```
myagent/                          # 主包
├── __init__.py                   # 包入口，导出主要类
├── config.py                     # 配置管理 (Pydantic Settings)
│   └── Settings                  # 配置类，管理数据目录、模型等
├── cli.py                        # 命令行界面 (Click)
│   ├── init                      # 初始化命令
│   ├── serve                     # 启动 MCP 服务器
│   ├── status                    # 查看状态
│   ├── remember                  # 直接保存记忆
│   ├── recall                    # 直接搜索记忆
│   └── config                    # 查看配置
├── mcp_server.py                 # MCP 服务器实现
│   └── MyAgentMCPServer          # MCP 协议处理器
├── core/                         # 核心功能（预留）
│   └── __init__.py
├── memory/                       # 记忆系统
│   ├── __init__.py
│   └── store.py                  # 记忆存储实现
│       ├── Memory                # 记忆数据类
│       └── MemoryStore           # 混合存储 (SQLite + Chroma)
├── skills/                       # 技能系统
│   ├── __init__.py
│   ├── base.py                   # 技能基类
│   │   ├── SkillInfo             # 技能信息
│   │   ├── Skill                 # 技能类
│   │   └── parse_skill_md        # SKILL.md 解析
│   └── registry.py               # 技能注册表
│       ├── SkillRegistry         # 技能发现和加载
│       └── tool                  # 工具装饰器
├── tools/                        # 工具系统
│   ├── __init__.py
│   ├── registry.py               # 工具注册表
│   │   ├── ToolSpec              # 工具规格
│   │   ├── ToolRegistry          # 工具管理
│   │   └── register_tool         # 注册装饰器
│   ├── memory_tools.py           # 记忆相关工具
│   │   ├── recall_memory
│   │   ├── save_memory
│   │   ├── list_recent_memories
│   │   ├── forget_memory
│   │   └── get_memory_stats
│   └── skill_tools.py            # 技能相关工具
│       ├── list_skills
│       ├── get_skill_info
│       ├── reload_skills
│       └── get_skills_directory
└── prompt/                       # 提示词组装
    ├── __init__.py
    └── assembler.py              # 提示词构建
        └── PromptAssembler       # 整合记忆和技能上下文

skills/                           # 示例技能目录
├── code_assistant/               # 代码助手技能
│   ├── SKILL.md                  # 技能定义
│   └── tools.py                  # 工具实现
│       ├── save_snippet
│       ├── search_snippets
│       └── get_best_practices
└── personal_assistant/           # 个人助手技能
    ├── SKILL.md
    └── tools.py
        ├── save_preference
        ├── get_preferences
        └── remind_me

data/                             # 数据目录（运行时创建）
├── memories.db                   # SQLite 元数据
└── chroma/                       # ChromaDB 向量存储

pyproject.toml                    # 项目配置和依赖
README.md                         # 项目说明
QUICKSTART.md                     # 快速开始指南
PROJECT_STRUCTURE.md              # 本文件
mcp-config-example.json           # MCP 配置示例
install.sh                        # 安装脚本
Makefile                          # 常用命令
