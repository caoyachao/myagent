"""Long-term memory storage with SQLite and ChromaDB."""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
import hashlib

import chromadb
from chromadb.config import Settings as ChromaSettings

from myagent.config import get_settings


# Singleton instance
_memory_store_instance: Optional['MemoryStore'] = None


def get_memory_store() -> 'MemoryStore':
    """Get the singleton MemoryStore instance."""
    global _memory_store_instance
    if _memory_store_instance is None:
        _memory_store_instance = MemoryStore()
    return _memory_store_instance


@dataclass
class Memory:
    """A single memory entry."""
    id: str
    content: str
    memory_type: str  # 'fact', 'preference', 'event', 'insight', 'code'
    source: str  # Where this memory came from
    created_at: datetime
    updated_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    tags: List[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}


class MemoryStore:
    """Hybrid memory store using SQLite for metadata and Chroma for vectors."""
    
    def __init__(self):
        self.settings = get_settings()
        self._init_sqlite()
        self._init_chroma()
    
    def _init_sqlite(self):
        """Initialize SQLite database for metadata."""
        self.db_path = self.settings.memory_db_path
        with self._get_db() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    tags TEXT,  -- JSON array
                    metadata TEXT  -- JSON object
                )
            """)
            
            # Create indices for faster queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source ON memories(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_created ON memories(created_at)")
            conn.commit()
    
    def _init_chroma(self):
        """Initialize ChromaDB for vector storage."""
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.chroma_client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"}
        )
    
    @contextmanager
    def _get_db(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID from content."""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def add(self, content: str, memory_type: str = "fact", source: str = "user",
            tags: Optional[List[str]] = None, metadata: Optional[Dict] = None) -> str:
        """Add a new memory."""
        memory_id = self._generate_id(content + str(datetime.now()))
        now = datetime.now()
        
        tags_json = json.dumps(tags or [])
        metadata_json = json.dumps(metadata or {})
        
        # Store in SQLite
        with self._get_db() as conn:
            conn.execute(
                """INSERT INTO memories 
                   (id, content, memory_type, source, created_at, updated_at, tags, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (memory_id, content, memory_type, source, now, now, tags_json, metadata_json)
            )
            conn.commit()
        
        # Store in Chroma (embedding happens automatically via embedding function)
        self.collection.add(
            documents=[content],
            metadatas=[{
                "memory_type": memory_type,
                "source": source,
                "created_at": now.isoformat(),
            }],
            ids=[memory_id]
        )
        
        return memory_id
    
    def get(self, memory_id: str) -> Optional[Memory]:
        """Get a memory by ID."""
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM memories WHERE id = ?", (memory_id,)
            ).fetchone()
            
            if row is None:
                return None
            
            return self._row_to_memory(row)
    
    def search(self, query: str, top_k: int = None, 
               memory_type: Optional[str] = None) -> List[Memory]:
        """Search memories by semantic similarity."""
        if top_k is None:
            top_k = self.settings.max_memories_per_query
        
        # Build where filter
        where_filter = None
        if memory_type:
            where_filter = {"memory_type": memory_type}
        
        # Query Chroma
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
        )
        
        if not results["ids"] or not results["ids"][0]:
            return []
        
        # Fetch full records from SQLite
        memory_ids = results["ids"][0]
        memories = []
        
        with self._get_db() as conn:
            for mid in memory_ids:
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = ?", (mid,)
                ).fetchone()
                if row:
                    memories.append(self._row_to_memory(row))
        
        return memories
    
    def update_access(self, memory_id: str):
        """Update access count and timestamp."""
        now = datetime.now()
        with self._get_db() as conn:
            conn.execute(
                """UPDATE memories 
                   SET access_count = access_count + 1, last_accessed = ?
                   WHERE id = ?""",
                (now, memory_id)
            )
            conn.commit()
    
    def list_recent(self, limit: int = 20, memory_type: Optional[str] = None) -> List[Memory]:
        """List recent memories."""
        query = "SELECT * FROM memories"
        params = []
        
        if memory_type:
            query += " WHERE memory_type = ?"
            params.append(memory_type)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_memory(row) for row in rows]
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        with self._get_db() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
        
        if deleted:
            self.collection.delete(ids=[memory_id])
        
        return deleted
    
    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert SQLite row to Memory object."""
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
            metadata=json.loads(row["metadata"] or "{}")
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        with self._get_db() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            by_type = {}
            for row in conn.execute("SELECT memory_type, COUNT(*) FROM memories GROUP BY memory_type"):
                by_type[row[0]] = row[1]
        
        return {
            "total_memories": total,
            "by_type": by_type,
            "embedding_model": self.settings.embedding_model,
        }
