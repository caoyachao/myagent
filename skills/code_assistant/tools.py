"""Tools for code assistant skill."""

from myagent.agent.manager import get_agent_manager
from myagent.memory.agent_store import AgentAwareMemoryStore
from myagent.skills.registry import tool


def _get_memory_store() -> AgentAwareMemoryStore:
    """Get the current agent's memory store."""
    agent_manager = get_agent_manager()
    return AgentAwareMemoryStore(agent_manager)


@tool()
def save_snippet(code: str, language: str, description: str = "", tags: list = None) -> str:
    """
    Save a code snippet to the knowledge base.
    
    Args:
        code: The code snippet
        language: Programming language
        description: Brief description
        tags: Optional tags
    """
    store = _get_memory_store()
    
    content = f"[{language}] {description}\n\n{code}" if description else f"[{language}]\n{code}"
    
    all_tags = ["snippet", language]
    if tags:
        all_tags.extend(tags)
    
    memory_id = store.add(
        content=content,
        memory_type="code",
        source="code_assistant_skill",
        tags=all_tags
    )
    
    return f"Code snippet saved (ID: {memory_id})"


@tool()
def search_snippets(query: str, language: str = None, top_k: int = 5) -> str:
    """
    Search for code snippets.
    
    Args:
        query: Search query
        language: Filter by language
        top_k: Number of results
    """
    store = _get_memory_store()
    
    # Enhance query for code search
    enhanced_query = f"code snippet {query}"
    
    memories = store.search(enhanced_query, top_k=top_k * 2, memory_type="code")
    
    # Filter by language if specified
    if language:
        memories = [m for m in memories if language.lower() in m.content.lower()]
    
    memories = memories[:top_k]
    
    if not memories:
        return "No matching code snippets found."
    
    lines = [f"Found {len(memories)} code snippets:"]
    for i, mem in enumerate(memories, 1):
        lines.append(f"\n--- Snippet {i} ---")
        lines.append(mem.content)
        if mem.tags:
            lines.append(f"Tags: {', '.join(mem.tags)}")
    
    return "\n".join(lines)


@tool()
def get_best_practices(language: str, topic: str = None) -> str:
    """
    Get best practices for a programming language.
    
    Args:
        language: Programming language
        topic: Specific topic (e.g., 'error handling', 'testing')
    """
    store = _get_memory_store()
    
    query = f"{language} best practices"
    if topic:
        query += f" {topic}"
    
    memories = store.search(query, top_k=5)
    
    # Filter for insights and preferences related to coding
    relevant = [
        m for m in memories 
        if m.memory_type in ["insight", "preference", "fact"]
        and language.lower() in m.content.lower()
    ]
    
    if not relevant:
        return f"No specific best practices recorded for {language}."
    
    lines = [f"Best practices for {language}:"]
    for mem in relevant:
        lines.append(f"\n• {mem.content}")
    
    return "\n".join(lines)
