#!/usr/bin/env python3
"""Tests for memory archiving functionality."""

import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))


def create_test_memory(content: str, memory_type: str = "fact", 
                       days_old: int = 0, access_count: int = 0) -> "Memory":
    """Create a test memory with specified age."""
    from myagent.memory.store import Memory
    
    created_at = datetime.now() - timedelta(days=days_old)
    
    return Memory(
        id=f"test_{hash(content) % 100000:05d}",
        content=content,
        memory_type=memory_type,
        source="test",
        created_at=created_at,
        updated_at=created_at,
        access_count=access_count,
        tags=["test"],
        metadata={},
        agent_id="test_agent"
    )


def test_archiver_init():
    """Test MemoryArchiver initialization."""
    print("Testing MemoryArchiver initialization...")
    
    from myagent.memory.archiver import MemoryArchiver
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        assert archiver.agent_id == "test_agent"
        assert archiver._archive_dir.exists()
        print("✓ Archiver initialized")
        return True


def test_activity_score():
    """Test activity score calculation."""
    print("\nTesting activity score calculation...")
    
    from myagent.memory.archiver import MemoryArchiver
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        # Recent, high access = high score
        recent_hot = create_test_memory("recent hot", days_old=5, access_count=10)
        score1 = archiver._calculate_activity_score(recent_hot)
        
        # Old, low access = low score
        old_cold = create_test_memory("old cold", days_old=100, access_count=0)
        score2 = archiver._calculate_activity_score(old_cold)
        
        assert score1 > score2, f"Recent hot should score higher: {score1} vs {score2}"
        print(f"✓ Activity scores: recent={score1:.2f}, old={score2:.2f}")
        return True


def test_tier_distribution():
    """Test memory tier distribution."""
    print("\nTesting tier distribution...")
    
    from myagent.memory.archiver import MemoryArchiver
    import sqlite3
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        # Create test database with memories
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                source TEXT NOT NULL,
                agent_id TEXT DEFAULT 'test_agent',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP,
                tags TEXT,
                metadata TEXT
            )
        """)
        
        # Insert test memories
        now = datetime.now()
        test_memories = [
            # Hot: recent, high access (need >= 3 for hot threshold)
            ("hot1", "Hot memory 1", now - timedelta(days=5), 5),
            ("hot2", "Hot memory 2", now - timedelta(days=10), 8),
            # Warm: moderately old, some access (need >= 1 for warm threshold)
            ("warm1", "Warm memory 1", now - timedelta(days=40), 2),
            # Cold: old, no access
            ("cold1", "Cold memory 1", now - timedelta(days=100), 0),
            ("cold2", "Cold memory 2", now - timedelta(days=120), 0),
        ]
        
        for mid, content, created, access in test_memories:
            conn.execute(
                """INSERT INTO memories 
                   (id, content, memory_type, source, agent_id, created_at, updated_at, access_count, last_accessed, tags, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (mid, content, "fact", "test", "test_agent", 
                 created.isoformat(), created.isoformat(), access, None,
                 '[]', '{}')
            )
        conn.commit()
        conn.close()
        
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        distribution = archiver.analyze_distribution()
        
        print(f"  Hot: {len(distribution.hot)}")
        print(f"  Warm: {len(distribution.warm)}")
        print(f"  Cold: {len(distribution.cold)}")
        
        # Verify distribution
        assert len(distribution.hot) == 2, f"Expected 2 hot, got {len(distribution.hot)}"
        assert len(distribution.cold) == 2, f"Expected 2 cold, got {len(distribution.cold)}"
        
        print("✓ Tier distribution correct")
        return True


def test_compression_summary():
    """Test summary compression strategy."""
    print("\nTesting summary compression...")
    
    from myagent.memory.archiver import MemoryArchiver
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        # Create test memories from same time window
        now = datetime.now()
        memories = [
            create_test_memory(f"Memory {i}", days_old=100, access_count=0)
            for i in range(5)
        ]
        # Set all to same creation time
        for m in memories:
            m.created_at = now - timedelta(days=100)
        
        result = archiver._compress_by_summary(memories)
        
        print(f"  Original: {result.original_count}")
        print(f"  Compressed: {result.compressed_count}")
        print(f"  Strategy: {result.strategy_used}")
        
        assert result.original_count == 5
        assert result.compressed_count <= result.original_count
        assert len(result.archived_files) > 0
        
        print("✓ Summary compression works")
        return True


def test_dedup_compression():
    """Test deduplication compression."""
    print("\nTesting dedup compression...")
    
    from myagent.memory.archiver import MemoryArchiver
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        # Create duplicate memories
        memories = [
            create_test_memory("Duplicate content", days_old=100),
            create_test_memory("Duplicate content", days_old=101),  # Same content
            create_test_memory("Duplicate content", days_old=102),  # Same content
            create_test_memory("Unique content", days_old=100),
        ]
        
        result = archiver._compress_by_dedup(memories)
        
        print(f"  Original: {result.original_count}")
        print(f"  After dedup: {result.compressed_count}")
        
        assert result.compressed_count < result.original_count
        assert result.compressed_count == 2  # 2 unique
        
        print("✓ Deduplication works")
        return True


def test_archive_search():
    """Test searching archived memories."""
    print("\nTesting archive search...")
    
    from myagent.memory.archiver import MemoryArchiver
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        # Create and archive some memories
        memories = [
            create_test_memory("Python programming tips", days_old=100),
            create_test_memory("JavaScript async patterns", days_old=101),
            create_test_memory("Python best practices", days_old=102),
        ]
        
        archiver._archive_memories(memories)
        
        # Search
        results = archiver.search_archive("python", top_k=5)
        
        print(f"  Search 'python': {len(results)} results")
        
        # Should find at least the 2 Python-related memories
        assert len(results) >= 2, f"Expected at least 2 results, got {len(results)}"
        
        print("✓ Archive search works")
        return True


def test_full_maintenance():
    """Test full maintenance workflow."""
    print("\nTesting full maintenance...")
    
    from myagent.memory.archiver import MemoryArchiver
    import sqlite3
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        
        # Create test database
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                source TEXT NOT NULL,
                agent_id TEXT DEFAULT 'test_agent',
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP,
                tags TEXT,
                metadata TEXT
            )
        """)
        
        # Insert mix of memories
        now = datetime.now()
        for i in range(5):
            # Hot memories
            conn.execute(
                """INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"hot_{i}", f"Hot {i}", "fact", "test", "test_agent",
                 (now - timedelta(days=5)).isoformat(),
                 (now - timedelta(days=5)).isoformat(),
                 5, None, '[]', '{}')
            )
        for i in range(3):
            # Cold memories
            conn.execute(
                """INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"cold_{i}", f"Cold {i}", "fact", "test", "test_agent",
                 (now - timedelta(days=100)).isoformat(),
                 (now - timedelta(days=100)).isoformat(),
                 0, None, '[]', '{}')
            )
        conn.commit()
        conn.close()
        
        archiver = MemoryArchiver(
            agent_id="test_agent",
            db_path=db_path,
            chroma_path=None
        )
        
        stats = archiver.run_maintenance()
        
        print(f"  Total analyzed: {stats['analysis']['total']}")
        print(f"  Hot: {stats['analysis']['hot']}")
        print(f"  Cold: {stats['analysis']['cold']}")
        print(f"  Archived: {stats['compression'].get('original_count', 0)}")
        print(f"  Deleted: {stats['cleanup'].get('deleted_from_active', 0)}")
        
        assert stats['analysis']['total'] == 8
        assert stats['cleanup'].get('deleted_from_active', 0) > 0
        
        print("✓ Full maintenance works")
        return True


def main():
    """Run all archive tests."""
    print("=" * 50)
    print("Memory Archive Tests")
    print("=" * 50)
    
    tests = [
        test_archiver_init,
        test_activity_score,
        test_tier_distribution,
        test_compression_summary,
        test_dedup_compression,
        test_archive_search,
        test_full_maintenance,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
