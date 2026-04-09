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
        """Recall memories.
        
        Args:
            query: The search query
            top_k: Number of results to return
            memory_type: Filter by memory type
            include_master: Whether to include master agent memories. 
                          Defaults to True (always search master memories).
                          Set to False to exclude master memories.
        """
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
            lines.append(f"{i}. [ID: {mem.id}] [{mem.memory_type}] {mem.content}")
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
        """Save a memory to current agent's memory store.
        
        By default, memories are ONLY saved to the current agent's database.
        They will NOT be shared with master unless explicitly requested.
        """
        if not content or not content.strip():
            return "Error: Content cannot be empty."
        
        # Normalize tags
        if tags is None:
            tags = []
        elif isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        
        # SECURITY: Only save to current agent's memory by default
        # Master memory is never modified unless explicitly requested
        memory_id = self.memory_store.add(
            content=content.strip(),
            memory_type=memory_type,
            source=self.agent.name,
            tags=tags,
            share_with_master=share_with_master
        )
        
        if self.agent.is_master:
            result = f"✅ Memory saved to master (ID: {memory_id})."
        elif share_with_master:
            result = f"✅ Memory saved to {self.agent.name} and shared with master (ID: {memory_id})."
        else:
            result = f"✅ Memory saved to {self.agent.name} only (ID: {memory_id})."
        
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
            lines.append(f"• [ID: {mem.id}] [{date}] [{mem.memory_type}] {mem.content[:80]}...")
        
        return "\n".join(lines)
    
    def forget(self, memory_id: str) -> str:
        """Delete a memory from current agent's memory store.
        
        Security: Can only delete memories from current agent's database.
        Cannot delete master agent's memories unless current agent is master.
        """
        if not memory_id:
            return "Error: Memory ID cannot be empty."
        
        # Check if memory exists in current agent's store
        memory = self.memory_store.get(memory_id)
        if memory is None:
            return f"Memory {memory_id} not found in {self.agent.name}'s memory store."
        
        # Security check: can only delete own memories
        if memory.agent_id and memory.agent_id != self.agent.id:
            return f"⚠️ Cannot delete: Memory {memory_id} belongs to a different agent. You can only delete memories from {self.agent.name}."
        
        if self.memory_store.delete(memory_id):
            return f"✅ Memory {memory_id} deleted from {self.agent.name}.'"
        else:
            return f"Failed to delete memory {memory_id}."
    
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