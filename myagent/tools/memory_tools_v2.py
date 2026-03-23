"""Memory management tools for MyAgent 2.0."""

from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from myagent.memory.agent_store import AgentAwareMemoryStore
    from myagent.agent.models import Agent


class MemoryToolsV2:
    """Memory tools that work with agent-aware storage."""
    
    def __init__(self, memory_store: "AgentAwareMemoryStore", agent: "Agent"):
        self.memory_store = memory_store
        self.agent = agent
    
    def recall(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        include_master: Optional[bool] = None
    ) -> str:
        """Recall memories."""
        if not query or not query.strip():
            return "Error: Query cannot be empty."
        
        memories = self.memory_store.search(
            query=query,
            top_k=top_k,
            memory_type=memory_type,
            include_master=include_master
        )
        
        if not memories:
            return f"No relevant memories found for '{query}'."
        
        lines = [f"Found {len(memories)} relevant memories:\n"]
        
        for i, mem in enumerate(memories, 1):
            lines.append(f"{i}. [{mem.memory_type}] {mem.content}")
            if mem.tags:
                lines.append(f"   Tags: {', '.join(mem.tags)}")
            if mem.source:
                lines.append(f"   Source: {mem.source}")
        
        return "\n".join(lines)
    
    def save(
        self,
        content: str,
        memory_type: str = "fact",
        tags: Optional[List[str]] = None,
        share_with_master: bool = False
    ) -> str:
        """Save a memory."""
        if not content or not content.strip():
            return "Error: Content cannot be empty."
        
        # Normalize tags
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        
        memory_id = self.memory_store.add(
            content=content.strip(),
            memory_type=memory_type,
            source=self.agent.name,
            tags=tags,
            share_with_master=share_with_master
        )
        
        result = f"✅ Memory saved (ID: {memory_id})."
        if share_with_master and not self.agent.is_master:
            result += " Also shared with master agent."
        
        return result
    
    def list_recent(
        self,
        limit: int = 10,
        memory_type: Optional[str] = None
    ) -> str:
        """List recent memories."""
        memories = self.memory_store.list_recent(
            limit=limit,
            memory_type=memory_type
        )
        
        if not memories:
            return "No memories found."
        
        lines = [f"Recent memories ({len(memories)}):\n"]
        
        for mem in memories:
            date = mem.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"• [{date}] [{mem.memory_type}] {mem.content[:80]}...")
        
        return "\n".join(lines)
    
    def forget(self, memory_id: str) -> str:
        """Delete a memory."""
        if not memory_id:
            return "Error: Memory ID cannot be empty."
        
        if self.memory_store.delete(memory_id):
            return f"Memory {memory_id} deleted successfully."
        else:
            return f"Memory {memory_id} not found."
    
    def get_stats(self) -> str:
        """Get memory statistics."""
        stats = self.memory_store.get_stats()
        
        lines = [
            f"Memory Statistics for {stats['agent_name']}:",
            f"Total memories: {stats['total_memories']}",
            f"Embedding model: {stats['embedding_model']}",
        ]
        
        if stats['by_type']:
            lines.append("By type:")
            for mem_type, count in stats['by_type'].items():
                lines.append(f"  • {mem_type}: {count}")
        
        return "\n".join(lines)