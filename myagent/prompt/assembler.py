"""Prompt assembler for building system prompts with memory and skills."""

from typing import List, Optional

from myagent.agent.manager import get_agent_manager
from myagent.memory.agent_store import AgentAwareMemoryStore
from myagent.skills.registry import SkillRegistry


class PromptAssembler:
    """Assemble system prompts with memory, skills, and tools context."""
    
    def __init__(self):
        self.agent_manager = get_agent_manager()
        self.memory_store = AgentAwareMemoryStore(self.agent_manager)
        self.skill_registry = SkillRegistry()
    
    def assemble_system_prompt(self, user_context: str = "") -> str:
        """
        Assemble a comprehensive system prompt.
        
        Args:
            user_context: Additional context from the user
        """
        sections = [
            self._get_base_prompt(),
            self._get_skill_installation_rules(),
            self._get_user_profile(),
            self._get_relevant_memories(user_context),
            self._get_available_skills(),
            self._get_available_tools(),
        ]
        
        if user_context:
            sections.append(f"【当前上下文】\n{user_context}")
        
        return "\n\n".join(sections)
    
    def _get_base_prompt(self) -> str:
        """Get the base system prompt."""
        return """你是一个有长期记忆的 AI 助手。你可以访问用户的历史记忆、已学习的技能和可用工具。

重要原则：
1. 主动检索相关记忆来提供个性化回复
2. 当用户提到过去的事情时，使用 recall_memory 工具检索
3. 重要的信息（如偏好、习惯、重要事实）使用 save_memory 保存
4. 利用可用技能来更好地完成任务

记忆类型说明：
- fact: 客观事实和知识
- preference: 用户偏好和习惯
- event: 特定事件和经历
- insight: 洞察和总结
- code: 代码片段和技术方案"""
    
    def _get_skill_installation_rules(self) -> str:
        """Get strict rules for skill installation."""
        return """【🔴 强制规则 - Skill 安装】

当用户说"安装 skill"、"装个 skill"或类似表述时，执行顺序必须如下：

1️⃣ 首选（强制）: 使用 install_skill MCP 工具
   - 询问用户范围: 共享(shared) 或 私有(private)
   - 调用 install_skill(slug, scope)
   
2️⃣ 次选（仅当 MCP 不可用时）: 使用 myagent CLI
   - myagent skill install <slug> [--shared|--private]

3️⃣ 禁止（除非以上都失败）: 直接使用 clawhub install
   - 这会绕过 MyAgent 的 Agent 身份系统
   - 安装的 Skill 无法与当前 Agent 关联

安装完成后，必须：
- 调用 list_skills() 验证安装成功
- 告知用户 Skill 的安装位置和可用范围

【为什么优先使用 MyAgent？】
✓ 与当前 Agent 身份绑定
✓ 支持共享/私有范围选择  
✓ 跨 CLI 一致体验（Kimi/Claude 等）
✓ 统一的 Skill 管理和更新"""
    
    def _get_user_profile(self) -> str:
        """Get user profile from memories."""
        # Retrieve preference-type memories to build profile
        prefs = self.memory_store.search(
            "user preferences habits style",
            top_k=10,
            memory_type="preference"
        )
        
        if not prefs:
            return "【用户画像】\n暂无足够信息构建用户画像。"
        
        lines = ["【用户画像】"]
        for pref in prefs[:5]:
            lines.append(f"• {pref.content}")
        
        return "\n".join(lines)
    
    def _get_relevant_memories(self, context: str, top_k: int = 8) -> str:
        """Get memories relevant to current context."""
        if not context:
            # Get recent memories instead
            recent = self.memory_store.list_recent(limit=5)
            if not recent:
                return "【近期记忆】\n暂无近期记忆。"
            
            lines = ["【近期记忆】"]
            for mem in recent:
                lines.append(f"• [{mem.memory_type}] {mem.content}")
            
            return "\n".join(lines)
        
        # Search for relevant memories
        memories = self.memory_store.search(context, top_k=top_k)
        
        if not memories:
            return "【相关记忆】\n未找到与当前话题相关的记忆。"
        
        lines = ["【相关记忆】"]
        for mem in memories:
            lines.append(f"• [{mem.memory_type}] {mem.content}")
        
        return "\n".join(lines)
    
    def _get_available_skills(self) -> str:
        """Get list of available skills."""
        skills = self.skill_registry.list_all()
        
        if not skills:
            return "【可用技能】\n暂无已加载的技能。"
        
        lines = [f"【可用技能】(\u200b{len(skills)} 个)"]
        for skill in skills:
            lines.append(f"• {skill.name}: {skill.description}")
        
        return "\n".join(lines)
    
    def _get_available_tools(self) -> str:
        """Get list of available tools."""
        from myagent.tools.registry import get_tool_registry
        
        registry = get_tool_registry()
        tools = registry.list_all()
        
        lines = [f"【可用工具】(\u200b{len(tools)} 个)"]
        lines.append("你可以使用以下工具来完成任务（自动选择）：")
        
        for tool in tools:
            lines.append(f"• {tool.name}: {tool.description}")
        
        return "\n".join(lines)
    
    def get_context_for_query(self, query: str) -> str:
        """Get contextual information for a specific query."""
        return self._get_relevant_memories(query)
