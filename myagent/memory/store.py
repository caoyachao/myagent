"""Memory data model for MyAgent."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


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
    agent_id: Optional[str] = None  # For multi-agent support
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "tags": self.tags,
            "metadata": self.metadata,
            "agent_id": self.agent_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """Create Memory from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=data["memory_type"],
            source=data["source"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None,
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            agent_id=data.get("agent_id"),
        )
