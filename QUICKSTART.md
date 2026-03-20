# MyAgent 快速开始指南

## 1. 安装

### 方式一：使用 pip

```bash
cd /Users/yachaocao/Projects/MyAgent
pip install -e .
```

### 方式二：使用 install.sh

```bash
cd /Users/yachaocao/Projects/MyAgent
chmod +x install.sh
./install.sh
```

## 2. 初始化

```bash
myagent init
```

这会创建以下目录：
- `~/.local/share/myagent/` - 数据存储
- `~/.config/myagent/` - 配置文件
- `~/.config/myagent/skills/` - 技能目录

## 3. 配置 Kimi Code CLI

### 找到 Kimi CLI 配置目录

```bash
# 通常是以下之一：
~/.kimi/mcp.json
~/.config/kimi/mcp.json
```

### 添加 MyAgent MCP 配置

将 `mcp-config-example.json` 的内容添加到 Kimi CLI 的 MCP 配置中：

```json
{
  "mcpServers": {
    "myagent": {
      "command": "python3",
      "args": ["-m", "myagent.mcp_server"],
      "env": {
        "MYAGENT_DATA_DIR": "~/.local/share/myagent"
      }
    }
  }
}
```

### 验证配置

```bash
# 查看 MyAgent 状态
myagent status

# 应该看到类似输出：
# Memory Statistics
# - Total Memories: 0
# - By type: {}
# 
# Skills (2)
# - code_assistant
# - personal_assistant
```

## 4. 使用 MyAgent

### 启动 Kimi CLI

```bash
kimi
```

现在 MyAgent 的工具会自动可用。Kimi CLI 可以在适当时候调用：

- `recall_memory` - 检索相关记忆
- `save_memory` - 保存新记忆
- `list_skills` - 查看可用技能
- 等等...

### 直接操作记忆（可选）

你也可以在命令行直接管理记忆：

```bash
# 保存记忆
myagent remember "我喜欢用 Python 写代码" --type preference --tag coding

# 检索记忆
myagent recall "Python 编程"

# 查看统计
myagent status
```

## 5. 创建自定义技能

### 步骤 1：创建技能目录

```bash
mkdir -p ~/.config/myagent/skills/my_custom_skill
```

### 步骤 2：创建 SKILL.md

```bash
cat > ~/.config/myagent/skills/my_custom_skill/SKILL.md << 'EOF'
---
name: my_custom_skill
description: My custom skill for specific tasks
version: 1.0.0
author: me
tags: [custom, utility]
tools: [greet]
---

# My Custom Skill

This skill provides custom utilities.
EOF
```

### 步骤 3：创建 tools.py（可选）

```bash
cat > ~/.config/myagent/skills/my_custom_skill/tools.py << 'EOF'
from myagent.skills.registry import tool

@tool()
def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}! Welcome to MyAgent."
EOF
```

### 步骤 4：重新加载技能

```bash
myagent status
```

## 6. 工作原理

### 记忆流程

```
用户输入 → Kimi CLI → MyAgent MCP
                      ↓
              1. 检索相关记忆
              2. 组装增强提示词
              3. 添加可用工具
                      ↓
              发送到 Kimi API
                      ↓
              返回结果给用户
                      ↓
              保存重要信息到记忆
```

### 技能流程

```
1. MyAgent 启动时扫描 ~/.config/myagent/skills/
2. 解析每个 SKILL.md 文件
3. 加载对应的 tools.py
4. 通过 MCP 暴露工具给 Kimi CLI
5. Kimi CLI 根据需要调用工具
```

## 7. 配置选项

环境变量：

```bash
export MYAGENT_DATA_DIR="/custom/path"        # 数据目录
export MYAGENT_EMBEDDING_MODEL="model-name"   # 嵌入模型
export MYAGENT_LOG_LEVEL="DEBUG"              # 日志级别
```

## 8. 故障排除

### 问题：MyAgent 工具没有出现在 Kimi CLI

解决：
1. 检查 MCP 配置是否正确
2. 确保 myagent serve 可以正常运行
3. 重启 Kimi CLI

### 问题：记忆搜索不工作

解决：
1. 检查 ChromaDB 是否已初始化：
   ```bash
   ls ~/.local/share/myagent/chroma/
   ```
2. 确保已安装 sentence-transformers：
   ```bash
   pip install sentence-transformers
   ```

### 问题：技能没有加载

解决：
1. 检查技能目录结构
2. 确保 SKILL.md 格式正确（YAML frontmatter）
3. 运行 `myagent status` 查看加载的技能

## 9. 示例使用场景

### 场景 1：保存代码片段

```
用户：记住这个 Python 装饰器的写法
Kimi：> 调用 save_memory
      内容：Python 装饰器代码...
      类型：code
      标签：["python", "decorator"]
已保存代码片段！
```

### 场景 2：检索偏好

```
用户：用我喜欢的风格写这段代码
Kimi：> 调用 recall_memory("coding style preference")
      找到记忆："我喜欢函数式编程风格"
好的，我会用函数式风格来写...
```

### 场景 3：使用技能工具

```
用户：保存这段代码
Kimi：> 调用 save_snippet（来自 code_assistant 技能）
代码片段已保存！
```

## 10. 进阶配置

### 自定义嵌入模型

编辑 `~/.config/myagent/config.yaml`（如果不存在则创建）：

```yaml
embedding_model: "sentence-transformers/all-MiniLM-L6-v2"
max_memories_per_query: 15
memory_score_threshold: 0.4
```

### 备份记忆

```bash
# 备份数据目录
cp -r ~/.local/share/myagent ~/myagent-backup

# 恢复
cp -r ~/myagent-backup/* ~/.local/share/myagent/
```

---

**恭喜！** 现在你已经可以开始使用 MyAgent 来增强 Kimi Code CLI 的记忆和技能能力了。
