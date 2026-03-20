"""Built-in memory management tools."""

from typing import List, Optional

from myagent.memory.store import MemoryStore, get_memory_store
from myagent.tools.registry import register_tool


# Global memory store instance
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get or create global memory store."""
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


@register_tool(
    name="recall_memory",
    description="Search and retrieve relevant memories based on a query"
)
def recall_memory(query: str, top_k: int = 5, memory_type: Optional[str] = None) -> str:
    """
    Recall relevant memories based on semantic search.
    
    Args:
        query: The search query
        top_k: Number of memories to retrieve (default: 5)
        memory_type: Filter by memory type (fact, preference, event, insight, code)
    """
    store = get_memory_store()
    memories = store.search(query, top_k=top_k, memory_type=memory_type)
    
    if not memories:
        return "No relevant memories found."
    
    # Update access stats
    for mem in memories:
        store.update_access(mem.id)
    
    # Format results
    lines = ["Relevant memories:"]
    for i, mem in enumerate(memories, 1):
        lines.append(f"\n{i}. [{mem.memory_type}] {mem.content}")
        if mem.tags:
            lines.append(f"   Tags: {', '.join(mem.tags)}")
    
    return "\n".join(lines)


@register_tool(
    name="save_memory",
    description="Save important information to long-term memory"
)
def save_memory(content: str, memory_type: str = "fact", 
                tags: Optional[List[str]] = None) -> str:
    """
    Save information to long-term memory.
    
    Args:
        content: The information to save
        memory_type: Type of memory (fact, preference, event, insight, code)
        tags: Optional tags for categorization
    """
    store = get_memory_store()
    
    # Ensure tags is a list
    if tags is None:
        tags = []
    elif isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    
    memory_id = store.add(
        content=content,
        memory_type=memory_type,
        source="user",
        tags=tags
    )
    
    return f"Memory saved successfully (ID: {memory_id})."


@register_tool(
    name="list_recent_memories",
    description="List recently added memories"
)
def list_recent_memories(limit: int = 10, memory_type: Optional[str] = None) -> str:
    """
    List recently added memories.
    
    Args:
        limit: Maximum number of memories to return
        memory_type: Filter by memory type
    """
    store = get_memory_store()
    memories = store.list_recent(limit=limit, memory_type=memory_type)
    
    if not memories:
        return "No memories found."
    
    lines = [f"Recent memories ({len(memories)} total):"]
    for mem in memories:
        date = mem.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"\n• [{date}] [{mem.memory_type}] {mem.content[:80]}...")
    
    return "\n".join(lines)


@register_tool(
    name="forget_memory",
    description="Delete a memory by its ID"
)
def forget_memory(memory_id: str) -> str:
    """
    Delete a memory from the store.
    
    Args:
        memory_id: The ID of the memory to delete
    """
    store = get_memory_store()
    if store.delete(memory_id):
        return f"Memory {memory_id} deleted successfully."
    else:
        return f"Memory {memory_id} not found."


@register_tool(
    name="get_memory_stats",
    description="Get statistics about the memory store"
)
def get_memory_stats() -> str:
    """Get memory store statistics."""
    store = get_memory_store()
    stats = store.get_stats()
    
    lines = [
        "Memory Store Statistics:",
        f"- Total memories: {stats['total_memories']}",
        f"- Embedding model: {stats['embedding_model']}",
        "- By type:"
    ]
    
    for mem_type, count in stats['by_type'].items():
        lines.append(f"  • {mem_type}: {count}")
    
    return "\n".join(lines)
