"""Tools for personal assistant skill."""

from myagent.agent.manager import get_agent_manager
from myagent.memory.agent_store import AgentAwareMemoryStore
from myagent.skills.registry import tool


def _get_memory_store() -> AgentAwareMemoryStore:
    """Get the current agent's memory store."""
    agent_manager = get_agent_manager()
    return AgentAwareMemoryStore(agent_manager)


@tool()
def save_preference(category: str, preference: str, importance: str = "medium") -> str:
    """
    Save a user preference.
    
    Args:
        category: Category of preference (e.g., 'coding', 'communication', 'ui')
        preference: The preference description
        importance: 'high', 'medium', or 'low'
    """
    store = _get_memory_store()
    
    content = f"[{category}] {preference} (importance: {importance})"
    
    memory_id = store.add(
        content=content,
        memory_type="preference",
        source="personal_assistant_skill",
        tags=["preference", category, importance]
    )
    
    return f"Preference saved (ID: {memory_id})"


@tool()
def get_preferences(category: str = None, top_k: int = 10) -> str:
    """
    Get user preferences.
    
    Args:
        category: Filter by category
        top_k: Maximum number of preferences
    """
    store = _get_memory_store()
    
    memories = store.search(
        "preference" if category is None else f"preference {category}",
        top_k=top_k,
        memory_type="preference"
    )
    
    if not memories:
        return "No preferences recorded yet."
    
    lines = ["User Preferences:"]
    for mem in memories:
        lines.append(f"• {mem.content}")
    
    return "\n".join(lines)


@tool()
def remind_me(content: str, when: str = None) -> str:
    """
    Save a reminder.
    
    Args:
        content: What to remember
        when: When to be reminded (e.g., 'next meeting', 'tomorrow')
    """
    store = _get_memory_store()
    
    full_content = content
    if when:
        full_content = f"[Reminder for {when}] {content}"
    
    memory_id = store.add(
        content=full_content,
        memory_type="event",
        source="personal_assistant_skill",
        tags=["reminder"]
    )
    
    return f"Reminder saved (ID: {memory_id})"
