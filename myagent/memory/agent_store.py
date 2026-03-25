"""Agent-aware memory storage with isolation between agents."""

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

import chromadb
from chromadb.config import Settings as ChromaSettings

from myagent.agent.manager import AgentManager, get_agent_manager
from myagent.memory.store import Memory


# Thread-local storage for agent-specific context
_thread_local = threading.local()


class AgentAwareMemoryStore:
    """Memory store that respects agent boundaries and inheritance settings.
    
    This class is thread-safe. Each thread can have its own agent context,
    and concurrent access to shared resources is protected by locks.
    """
    
    def __init__(self, agent_manager: Optional[AgentManager] = None):
        self.agent_manager = agent_manager or get_agent_manager()
        self._lock = threading.RLock()
        
        # Storage resources per agent (cached)
        self._storage_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_lock = threading.RLock()
        
        # Initialize storage for current agent
        self._refresh_agent()
    
    def _get_current_agent(self):
        """Get current agent, either from thread-local or global manager."""
        # Check if thread has its own agent context
        if hasattr(_thread_local, 'agent_id'):
            agent = self.agent_manager.get_agent(_thread_local.agent_id)
            if agent:
                return agent
        
        # Fall back to global current agent
        return self.agent_manager.get_current_agent()
    
    def _refresh_agent(self):
        """Refresh current agent context."""
        with self._lock:
            self._current_agent = self._get_current_agent()
            self._init_storage()
    
    def _init_storage(self):
        """Initialize SQLite and ChromaDB for current agent."""
        agent = self._current_agent
        agent_id = agent.id
        
        # Check cache first
        with self._cache_lock:
            if agent_id in self._storage_cache:
                cache = self._storage_cache[agent_id]
                self.db_path = cache['db_path']
                self.chroma_path = cache['chroma_path']
                self.chroma_client = cache['chroma_client']
                self.collection = cache['collection']
                return
        
        # Initialize new storage
        # SQLite path
        self.db_path = agent.memory_db_path
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()
        
        # Chroma path
        self.chroma_path = agent.chroma_path
        if self.chroma_path:
            self.chroma_path.mkdir(parents=True, exist_ok=True)
            self._init_chroma()
        
        # Cache storage resources
        with self._cache_lock:
            self._storage_cache[agent_id] = {
                'db_path': self.db_path,
                'chroma_path': self.chroma_path,
                'chroma_client': getattr(self, 'chroma_client', None),
                'collection': getattr(self, 'collection', None),
            }
    
    def _init_sqlite(self):
        """Initialize SQLite database."""
        agent_id = self._current_agent.id
        with self._get_db() as conn:
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    agent_id TEXT DEFAULT '{agent_id}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    tags TEXT,
                    metadata TEXT
                )
            """)
            
            # Create indices
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON memories(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)")
            conn.commit()
    
    def _init_chroma(self):
        """Initialize ChromaDB."""
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Get or create collection with agent-specific name
        collection_name = f"memories_{self._current_agent.id}"
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={
                "hnsw:space": "cosine",
                "agent_id": self._current_agent.id
            }
        )
    
    @contextmanager
    def _get_db(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        import hashlib
        return hashlib.md5((content + str(datetime.now())).encode()).hexdigest()[:16]
    
    def add(self, content: str, memory_type: str = "fact", source: str = "user",
            tags: Optional[List[str]] = None, metadata: Optional[Dict] = None,
            share_with_master: bool = False) -> str:
        """
        Add a new memory to current agent.
        
        Args:
            share_with_master: If True, also save to master agent's memory
        """
        with self._lock:
            return self._add_unsafe(content, memory_type, source, tags, metadata, share_with_master)
    
    def _add_unsafe(self, content: str, memory_type: str, source: str,
                    tags: Optional[List[str]], metadata: Optional[Dict],
                    share_with_master: bool) -> str:
        """Add memory without acquiring lock (internal use only)."""
        memory_id = self._generate_id(content)
        now = datetime.now()
        
        tags_json = json.dumps(tags or [])
        metadata_json = json.dumps(metadata or {})
        agent_id = self._current_agent.id
        
        # Store in SQLite
        with self._get_db() as conn:
            conn.execute(
                """INSERT INTO memories 
                   (id, content, memory_type, source, agent_id, created_at, updated_at, tags, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (memory_id, content, memory_type, source, agent_id, now, now, tags_json, metadata_json)
            )
            conn.commit()
        
        # Store in Chroma
        self.collection.add(
            documents=[content],
            metadatas=[{
                "memory_type": memory_type,
                "source": source,
                "agent_id": agent_id,
                "created_at": now.isoformat(),
            }],
            ids=[memory_id]
        )
        
        # Optionally share with master
        if share_with_master and not self._current_agent.is_master:
            self._add_to_master(content, memory_type, source, tags, metadata)
        
        return memory_id
    
    def _add_to_master(self, content: str, memory_type: str, source: str,
                       tags: Optional[List[str]], metadata: Optional[Dict]):
        """Add memory to master agent."""
        master = self.agent_manager.get_agent("master")
        if not master:
            return
        
        # Create a temporary store for master
        # Note: This creates a new store instance to avoid lock contention
        master_store = AgentAwareMemoryStore(self.agent_manager)
        # Temporarily switch to master context
        with master_store._agent_context(master.id):
            master_store._add_unsafe(
                content, 
                memory_type, 
                f"{source} (from {self._current_agent.name})", 
                tags, 
                metadata,
                False  # Don't recursively share
            )
    
    @contextmanager
    def _agent_context(self, agent_id: str):
        """Temporarily switch to a different agent context."""
        previous_agent_id = getattr(_thread_local, 'agent_id', None)
        _thread_local.agent_id = agent_id
        try:
            self._refresh_agent()
            yield
        finally:
            if previous_agent_id is None:
                delattr(_thread_local, 'agent_id')
            else:
                _thread_local.agent_id = previous_agent_id
            self._refresh_agent()
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID from current agent (thread-safe)."""
        with self._lock:
            return self._get_unsafe(memory_id)
    
    def _get_unsafe(self, memory_id: str) -> Optional[Memory]:
        """Get memory without acquiring lock (internal use only)."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ? AND agent_id = ?",
                (memory_id, self._current_agent.id)
            ).fetchone()
            
            if row is None:
                return None
            
            return self._row_to_memory(row)
    
    def search(self, query: str, top_k: int = 5,
               memory_type: Optional[str] = None,
               include_master: bool = None) -> List[Memory]:
        """
        Search memories by semantic similarity (thread-safe).
        
        Args:
            include_master: If None or True, include master agent memories.
                          Set to False to exclude master memories.
        """
        with self._lock:
            return self._search_unsafe(query, top_k, memory_type, include_master)
    
    def _search_unsafe(self, query: str, top_k: int,
                       memory_type: Optional[str],
                       include_master: Optional[bool]) -> List[Memory]:
        """Search memories without acquiring lock (internal use only)."""
        # Default to True to always include master memories unless explicitly disabled
        if include_master is None:
            include_master = True
        
        results = []
        
        # Search current agent's memories
        agent_results = self._search_agent_memories(
            self._current_agent, query, top_k, memory_type
        )
        results.extend(agent_results)
        
        # Search master memories if configured
        if include_master and not self._current_agent.is_master:
            master = self.agent_manager.get_agent("master")
            if master:
                master_results = self._search_agent_memories(
                    master, query, top_k // 2, memory_type  # Fewer results from master
                )
                results.extend(master_results)
        
        # Sort by relevance (we'll use a simple approach - in production might want better scoring)
        # For now, just deduplicate and limit
        seen_ids = set()
        unique_results = []
        for mem in results:
            if mem.id not in seen_ids:
                seen_ids.add(mem.id)
                unique_results.append(mem)
                if len(unique_results) >= top_k:
                    break
        
        # Update access stats
        for mem in unique_results:
            self._update_access_unsafe(mem.id)
        
        return unique_results
    
    def _search_agent_memories(self, agent, query: str, top_k: int,
                               memory_type: Optional[str] = None) -> List[Memory]:
        """Search memories for a specific agent."""
        if agent.id == self._current_agent.id:
            # Use current collection
            collection = self.collection
            db_path = self.db_path
        else:
            # Need to open different collection
            chroma_path = agent.chroma_path
            if not chroma_path or not chroma_path.exists():
                return []
            
            client = chromadb.PersistentClient(
                path=str(chroma_path),
                settings=ChromaSettings(anonymized_telemetry=False)
            )
            collection_name = f"memories_{agent.id}"
            try:
                collection = client.get_collection(collection_name)
            except Exception:
                return []
            
            db_path = agent.memory_db_path
        
        # Build where filter
        where_filter = {"agent_id": agent.id}
        if memory_type:
            where_filter["memory_type"] = memory_type
        
        try:
            # Query Chroma
            chroma_results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter if memory_type else {"agent_id": agent.id}
            )
            
            if not chroma_results["ids"] or not chroma_results["ids"][0]:
                return []
            
            # Fetch full records from SQLite
            memory_ids = chroma_results["ids"][0]
            memories = []
            
            if db_path and db_path.exists():
                with sqlite3.connect(db_path) as conn:
                    conn.row_factory = sqlite3.Row
                    for mid in memory_ids:
                        row = conn.execute(
                            "SELECT * FROM memories WHERE id = ?", (mid,)
                        ).fetchone()
                        if row:
                            memories.append(self._row_to_memory(row))
            
            return memories
            
        except Exception as e:
            print(f"Error searching memories for agent {agent.id}: {e}")
            return []
    
    def list_recent(self, limit: int = 20, memory_type: Optional[str] = None) -> List[Memory]:
        """List recent memories for current agent (thread-safe)."""
        with self._lock:
            return self._list_recent_unsafe(limit, memory_type)
    
    def _list_recent_unsafe(self, limit: int, memory_type: Optional[str]) -> List[Memory]:
        """List recent memories without acquiring lock (internal use only)."""
        query = "SELECT * FROM memories WHERE agent_id = ?"
        params = [self._current_agent.id]
        
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory(row) for row in rows]
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory from current agent (thread-safe)."""
        with self._lock:
            return self._delete_unsafe(memory_id)
    
    def _delete_unsafe(self, memory_id: str) -> bool:
        """Delete memory without acquiring lock (internal use only)."""
        with self._get_db() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE id = ? AND agent_id = ?",
                (memory_id, self._current_agent.id)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
        
        if deleted:
            try:
                self.collection.delete(ids=[memory_id])
            except Exception:
                pass
        
        return deleted
    
    def update_access(self, memory_id: str):
        """Update access count and timestamp (thread-safe)."""
        with self._lock:
            self._update_access_unsafe(memory_id)
    
    def _update_access_unsafe(self, memory_id: str):
        """Update access without acquiring lock (internal use only)."""
        now = datetime.now()
        with self._get_db() as conn:
            conn.execute(
                """UPDATE memories 
                   SET access_count = access_count + 1, last_accessed = ?
                   WHERE id = ? AND agent_id = ?""",
                (now, memory_id, self._current_agent.id)
            )
            conn.commit()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics for current agent (thread-safe)."""
        with self._lock:
            return self._get_stats_unsafe()
    
    def _get_stats_unsafe(self) -> Dict[str, Any]:
        """Get stats without acquiring lock (internal use only)."""
        with self._get_db() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE agent_id = ?",
                (self._current_agent.id,)
            ).fetchone()[0]
            
            by_type = {}
            for row in conn.execute(
                "SELECT memory_type, COUNT(*) FROM memories WHERE agent_id = ? GROUP BY memory_type",
                (self._current_agent.id,)
            ):
                by_type[row[0]] = row[1]
        
        from myagent.config import get_settings
        return {
            "agent_id": self._current_agent.id,
            "agent_name": self._current_agent.name,
            "total_memories": total,
            "by_type": by_type,
            "embedding_model": get_settings().embedding_model,
        }
    
    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert SQLite row to Memory object."""
        # sqlite3.Row supports dict-like access but not .get()
        def get_col(row, col, default=None):
            try:
                return row[col]
            except (KeyError, IndexError):
                return default
        
        return Memory(
            id=row["id"],
            content=row["content"],
            memory_type=row["memory_type"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            access_count=row["access_count"],
            last_accessed=datetime.fromisoformat(row["last_accessed"]) if row["last_accessed"] else None,
            tags=json.loads(row["tags"] or "[]"),
            metadata=json.loads(row["metadata"] or "{}"),
            agent_id=get_col(row, "agent_id")
        )
    
    def refresh_agent(self):
        """Refresh current agent (call after switching)."""
        with self._lock:
            self._refresh_agent()
    
    def clear_cache(self):
        """Clear storage cache (useful for testing or memory management)."""
        with self._cache_lock:
            self._storage_cache.clear()
