"""Memory archiving and compression engine."""

import gzip
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple, Set
from collections import defaultdict

from myagent.memory.store import Memory
from myagent.config import get_settings


@dataclass
class CompressionResult:
    """Result of a compression operation."""
    original_count: int
    compressed_count: int
    strategy_used: str
    saved_bytes: int
    archived_files: List[str]


@dataclass
class MemoryTierDistribution:
    """Distribution of memories across tiers."""
    hot: List[Memory]
    warm: List[Memory]
    cold: List[Memory]
    
    @property
    def total(self) -> int:
        return len(self.hot) + len(self.warm) + len(self.cold)


class MemoryArchiver:
    """Archives and compresses memories to prevent unlimited growth.
    
    Uses a three-tier storage strategy:
    - Hot: Recent, frequently accessed memories (kept in active DB)
    - Warm: Older but occasionally accessed (kept in active DB, lower priority)
    - Cold: Old, rarely accessed (compressed and archived)
    """
    
    def __init__(self, agent_id: str, db_path: Path, chroma_path: Optional[Path] = None):
        self.agent_id = agent_id
        self.db_path = db_path
        self.chroma_path = chroma_path
        self.config = get_settings().archive
        self.settings = get_settings()
        
        self._lock = threading.RLock()
        self._archive_dir = self.settings.get_archive_dir(agent_id)
    
    def analyze_distribution(self) -> MemoryTierDistribution:
        """Analyze memory distribution across tiers."""
        all_memories = self._get_all_memories()
        
        now = datetime.now()
        hot_cutoff = now - timedelta(days=self.config.hot_days)
        warm_cutoff = now - timedelta(days=self.config.warm_days)
        
        hot_memories = []
        warm_memories = []
        cold_candidates = []
        
        for mem in all_memories:
            activity_score = self._calculate_activity_score(mem)
            
            # Hot: recent AND high activity
            if mem.created_at > hot_cutoff and activity_score >= self.config.hot_activity_threshold:
                hot_memories.append(mem)
            # Warm: moderately recent AND moderate activity
            elif mem.created_at > warm_cutoff and activity_score >= self.config.warm_activity_threshold:
                warm_memories.append(mem)
            # Cold: old AND rarely accessed
            else:
                cold_candidates.append(mem)
        
        return MemoryTierDistribution(
            hot=hot_memories,
            warm=warm_memories,
            cold=cold_candidates
        )
    
    def _get_all_memories(self) -> List[Memory]:
        """Get all memories from SQLite."""
        if not self.db_path.exists():
            return []
        
        memories = []
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM memories WHERE agent_id = ?",
                    (self.agent_id,)
                )
                for row in cursor.fetchall():
                    memories.append(self._row_to_memory(row))
        except Exception as e:
            print(f"Error loading memories: {e}")
        
        return memories
    
    def _calculate_activity_score(self, memory: Memory) -> float:
        """Calculate memory activity score (0-1+)."""
        age_days = (datetime.now() - memory.created_at).days
        recency = max(0, 1 - age_days / 90)  # Time decay
        access_score = min(memory.access_count / 10, 1.0)  # Access frequency
        
        # Importance weights by type
        importance_weights = {
            "preference": 1.5,
            "insight": 1.3,
            "code": 1.2,
            "event": 1.0,
            "fact": 0.9
        }
        type_weight = importance_weights.get(memory.memory_type, 1.0)
        
        return recency * 0.4 + access_score * 0.4 + (type_weight - 0.9) * 0.2
    
    def compress_memories(self, memories: List[Memory]) -> CompressionResult:
        """Compress memories using configured strategy."""
        if not memories:
            return CompressionResult(0, 0, "none", 0, [])
        
        strategy = self.config.compression_strategy
        
        if strategy == "summary":
            return self._compress_by_summary(memories)
        elif strategy == "merge":
            return self._compress_by_merge(memories)
        elif strategy == "dedup":
            return self._compress_by_dedup(memories)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
    
    def _compress_by_summary(self, memories: List[Memory]) -> CompressionResult:
        """Strategy: Group by time window and create summaries.
        
        Groups memories created within the same time window and
        creates a single summary memory for each group.
        """
        window_size = timedelta(days=7)
        groups = self._group_by_time_window(memories, window_size)
        
        compressed = []
        archived_files = []
        original_bytes = sum(len(m.content.encode()) for m in memories)
        
        for group in groups:
            if len(group) == 1:
                # Single memories go directly to archive
                compressed.append(group[0])
                continue
            
            # Create summary (simplified - in production could use LLM)
            summary = self._generate_summary(group)
            
            compressed_mem = Memory(
                id=self._generate_compressed_id(group),
                content=summary,
                memory_type="insight",  # Upgraded to insight
                source="compressed",
                created_at=group[0].created_at,
                updated_at=datetime.now(),
                access_count=sum(m.access_count for m in group),
                tags=list(set(t for m in group for t in m.tags)),
                metadata={
                    "compressed_from": [m.id for m in group],
                    "compression_type": "summary",
                    "original_count": len(group),
                    "original_ids": [m.id for m in group]
                },
                agent_id=self.agent_id
            )
            compressed.append(compressed_mem)
        
        # Archive compressed memories
        if compressed:
            archive_path = self._archive_memories(compressed)
            archived_files.append(archive_path)
        
        compressed_bytes = sum(len(m.content.encode()) for m in compressed)
        
        return CompressionResult(
            original_count=len(memories),
            compressed_count=len(compressed),
            strategy_used="summary",
            saved_bytes=original_bytes - compressed_bytes,
            archived_files=archived_files
        )
    
    def _group_by_time_window(self, memories: List[Memory], 
                              window: timedelta) -> List[List[Memory]]:
        """Group memories by time window."""
        if not memories:
            return []
        
        # Sort by creation time
        sorted_mems = sorted(memories, key=lambda m: m.created_at)
        
        groups = []
        current_group = [sorted_mems[0]]
        window_start = sorted_mems[0].created_at
        
        for mem in sorted_mems[1:]:
            if mem.created_at - window_start <= window:
                current_group.append(mem)
            else:
                groups.append(current_group)
                current_group = [mem]
                window_start = mem.created_at
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _generate_summary(self, memories: List[Memory]) -> str:
        """Generate a summary of multiple memories."""
        if len(memories) == 1:
            return memories[0].content
        
        # Group by type
        by_type = defaultdict(list)
        for m in memories:
            by_type[m.memory_type].append(m)
        
        parts = []
        
        # Summarize each type
        for mem_type, mems in sorted(by_type.items(), 
                                      key=lambda x: len(x[1]), 
                                      reverse=True):
            if len(mems) == 1:
                parts.append(f"[{mem_type}] {mems[0].content}")
            else:
                # List key points
                key_points = [m.content[:100] + "..." if len(m.content) > 100 else m.content 
                             for m in mems[:3]]
                parts.append(f"[{mem_type}] {len(mems)} related items: " + 
                           "; ".join(key_points))
                if len(mems) > 3:
                    parts[-1] += f" (and {len(mems)-3} more)"
        
        return "\n".join(parts)
    
    def _generate_compressed_id(self, memories: List[Memory]) -> str:
        """Generate ID for compressed memory."""
        import hashlib
        content = "".join(m.id for m in memories)
        return f"compressed_{hashlib.md5(content.encode()).hexdigest()[:12]}"
    
    def _compress_by_merge(self, memories: List[Memory]) -> CompressionResult:
        """Strategy: Merge semantically similar memories."""
        # Simple implementation: group by exact content similarity
        # In production, could use embeddings and clustering
        
        content_groups: Dict[str, List[Memory]] = defaultdict(list)
        for m in memories:
            # Normalize content for grouping
            key = m.content.lower().strip()[:100]
            content_groups[key].append(m)
        
        compressed = []
        for key, group in content_groups.items():
            if len(group) == 1:
                compressed.append(group[0])
            else:
                # Merge duplicates
                merged = self._merge_memories(group)
                compressed.append(merged)
        
        archived_files = []
        if compressed:
            archive_path = self._archive_memories(compressed)
            archived_files.append(archive_path)
        
        return CompressionResult(
            original_count=len(memories),
            compressed_count=len(compressed),
            strategy_used="merge",
            saved_bytes=0,
            archived_files=archived_files
        )
    
    def _merge_memories(self, memories: List[Memory]) -> Memory:
        """Merge similar memories into one."""
        # Pick the most accessed one as base
        base = max(memories, key=lambda m: m.access_count)
        
        return Memory(
            id=f"merged_{base.id}",
            content=base.content,
            memory_type=base.memory_type,
            source=f"merged ({len(memories)} sources)",
            created_at=min(m.created_at for m in memories),
            updated_at=datetime.now(),
            access_count=sum(m.access_count for m in memories),
            tags=list(set(t for m in memories for t in m.tags)),
            metadata={
                "merged_from": [m.id for m in memories],
                "compression_type": "merge",
                "merge_count": len(memories)
            },
            agent_id=self.agent_id
        )
    
    def _compress_by_dedup(self, memories: List[Memory]) -> CompressionResult:
        """Strategy: Remove exact and near-duplicate memories."""
        seen_hashes: Set[str] = set()
        unique_memories = []
        
        for m in memories:
            content_hash = hash(m.content.lower().strip())
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_memories.append(m)
        
        archived_files = []
        if unique_memories:
            archive_path = self._archive_memories(unique_memories)
            archived_files.append(archive_path)
        
        return CompressionResult(
            original_count=len(memories),
            compressed_count=len(unique_memories),
            strategy_used="dedup",
            saved_bytes=0,
            archived_files=archived_files
        )
    
    def _archive_memories(self, memories: List[Memory]) -> str:
        """Archive memories to compressed file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_file = self._archive_dir / f"archive_{timestamp}.jsonl.gz"
        
        # Serialize memories
        records = []
        for mem in memories:
            records.append(json.dumps(mem.to_dict(), ensure_ascii=False))
        
        # Compress and write
        jsonl_content = "\n".join(records)
        compressed = gzip.compress(
            jsonl_content.encode('utf-8'),
            compresslevel=self.config.compression_level
        )
        archive_file.write_bytes(compressed)
        
        return str(archive_file)
    
    def search_archive(self, query: str, top_k: int = 5) -> List[Memory]:
        """Search archived memories by keyword."""
        results = []
        query_lower = query.lower()
        
        for archive_file in self._archive_dir.glob("archive_*.jsonl.gz"):
            try:
                compressed = archive_file.read_bytes()
                jsonl_content = gzip.decompress(compressed).decode('utf-8')
                
                for line in jsonl_content.strip().split("\n"):
                    if not line:
                        continue
                    
                    data = json.loads(line)
                    content = data.get("content", "")
                    
                    # Simple keyword matching
                    if any(q in content.lower() for q in query_lower.split()):
                        results.append(Memory.from_dict(data))
            except Exception as e:
                print(f"Error reading archive {archive_file}: {e}")
        
        # Sort by relevance (access count as proxy)
        results.sort(key=lambda m: m.access_count, reverse=True)
        return results[:top_k]
    
    def delete_from_active(self, memory_ids: List[str]) -> int:
        """Delete memories from active storage."""
        if not self.db_path.exists() or not memory_ids:
            return 0
        
        deleted_count = 0
        try:
            with sqlite3.connect(self.db_path) as conn:
                for mid in memory_ids:
                    cursor = conn.execute(
                        "DELETE FROM memories WHERE id = ? AND agent_id = ?",
                        (mid, self.agent_id)
                    )
                    deleted_count += cursor.rowcount
                conn.commit()
        except Exception as e:
            print(f"Error deleting memories: {e}")
        
        # Also delete from Chroma if available
        if self.chroma_path and self.chroma_path.exists():
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
                
                client = chromadb.PersistentClient(
                    path=str(self.chroma_path),
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
                collection_name = f"memories_{self.agent_id}"
                try:
                    collection = client.get_collection(collection_name)
                    collection.delete(ids=memory_ids)
                except Exception:
                    pass
            except Exception:
                pass
        
        return deleted_count
    
    def run_maintenance(self) -> Dict[str, Any]:
        """Run full maintenance: analyze, compress, archive."""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "analysis": {},
            "compression": {},
            "cleanup": {},
        }
        
        # 1. Analyze distribution
        distribution = self.analyze_distribution()
        stats["analysis"] = {
            "hot": len(distribution.hot),
            "warm": len(distribution.warm),
            "cold": len(distribution.cold),
            "total": distribution.total
        }
        
        # 2. Handle capacity limits
        demoted_count = 0
        if len(distribution.hot) > self.config.max_hot_memories:
            excess = distribution.hot[self.config.max_hot_memories:]
            # Move excess to warm by updating timestamps
            demoted_count = len(excess)
        stats["cleanup"]["demoted_from_hot"] = demoted_count
        
        # 3. Compress and archive cold memories
        if distribution.cold:
            compression = self.compress_memories(distribution.cold)
            stats["compression"] = {
                "original_count": compression.original_count,
                "compressed_count": compression.compressed_count,
                "ratio": f"{(1 - compression.compressed_count/max(compression.original_count, 1))*100:.1f}%",
                "strategy": compression.strategy_used,
                "saved_bytes": compression.saved_bytes,
                "archived_files": compression.archived_files
            }
            
            # Delete archived memories from active storage
            deleted_ids = [m.id for m in distribution.cold]
            deleted_count = self.delete_from_active(deleted_ids)
            stats["cleanup"]["deleted_from_active"] = deleted_count
        
        # 4. Get archive stats
        archive_files = list(self._archive_dir.glob("archive_*.jsonl.gz"))
        stats["archive_stats"] = {
            "archive_count": len(archive_files),
            "total_size_mb": sum(f.stat().st_size for f in archive_files) / (1024 * 1024)
        }
        
        return stats
    
    def get_archive_stats(self) -> Dict[str, Any]:
        """Get statistics about archives."""
        archive_files = list(self._archive_dir.glob("archive_*.jsonl.gz"))
        
        total_memories = 0
        total_size = 0
        
        for f in archive_files:
            try:
                total_size += f.stat().st_size
                # Count lines (memories) in archive
                compressed = f.read_bytes()
                jsonl = gzip.decompress(compressed).decode('utf-8')
                total_memories += len([l for l in jsonl.split("\n") if l.strip()])
            except Exception:
                pass
        
        return {
            "archive_count": len(archive_files),
            "total_memories": total_memories,
            "total_size_mb": total_size / (1024 * 1024),
            "archive_dir": str(self._archive_dir)
        }
    
    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        """Convert SQLite row to Memory."""
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
