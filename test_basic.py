#!/usr/bin/env python3
"""Basic test for MyAgent core functionality."""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from myagent.config import get_settings
        print("✓ config")
        
        from myagent.memory.store import Memory
        print("✓ memory.store (Memory dataclass)")
        
        from myagent.memory.agent_store import AgentAwareMemoryStore
        print("✓ memory.agent_store")
        
        from myagent.skills.base import Skill, SkillInfo, parse_skill_md
        print("✓ skills.base")
        
        from myagent.skills.registry import SkillRegistry
        print("✓ skills.registry")
        
        from myagent.tools.registry import ToolRegistry, register_tool
        print("✓ tools.registry")
        
        from myagent.agent.manager import get_agent_manager
        print("✓ agent.manager")
        
        from myagent.agent.models import Agent, AgentCreateRequest
        print("✓ agent.models")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_skill_parsing():
    """Test SKILL.md parsing."""
    print("\nTesting skill parsing...")
    
    from myagent.skills.base import parse_skill_md
    
    skill_content = """---
name: test_skill
description: A test skill
version: 1.0.0
author: test
tags: [test, demo]
tools: [tool1, tool2]
---

# Test Skill

This is a test skill.
"""
    
    info = parse_skill_md(skill_content)
    
    if info is None:
        print("✗ Failed to parse skill")
        return False
    
    assert info.name == "test_skill", f"Expected 'test_skill', got '{info.name}'"
    assert info.version == "1.0.0"
    assert "test" in info.tags
    
    print(f"✓ Parsed skill: {info.name}")
    return True


def test_memory_data_model():
    """Test Memory dataclass."""
    print("\nTesting memory data model...")
    
    from myagent.memory.store import Memory
    from datetime import datetime
    
    try:
        mem = Memory(
            id="test123",
            content="Test content",
            memory_type="fact",
            source="test",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Test serialization
        data = mem.to_dict()
        assert data["id"] == "test123"
        assert data["content"] == "Test content"
        
        # Test deserialization
        mem2 = Memory.from_dict(data)
        assert mem2.id == mem.id
        assert mem2.content == mem.content
        
        print("✓ Memory dataclass works")
        return True
    except Exception as e:
        print(f"✗ Memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_manager():
    """Test AgentManager (basic operations)."""
    print("\nTesting AgentManager...")
    
    try:
        from myagent.agent.manager import get_agent_manager
        from myagent.agent.models import AgentCreateRequest
        
        manager = get_agent_manager()
        
        # Test getting current agent
        current = manager.get_current_agent()
        assert current is not None
        print(f"✓ Current agent: {current.name} (ID: {current.id}, is_master: {current.is_master})")
        
        # Test listing agents
        agents = manager.list_agents()
        assert len(agents) >= 1
        print(f"✓ Listed {len(agents)} agents")
        
        # Verify master agent exists
        master = manager.get_agent("master")
        assert master is not None
        assert master.is_master
        print(f"✓ Master agent exists: {master.name}")
        
        return True
    except Exception as e:
        print(f"✗ AgentManager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thread_safety():
    """Test thread safety of AgentManager."""
    print("\nTesting thread safety...")
    
    try:
        import threading
        from myagent.agent.manager import get_agent_manager
        
        manager = get_agent_manager()
        results = []
        errors = []
        
        # Get current agent ID for comparison
        current = manager.get_current_agent()
        current_id = current.id
        
        def worker():
            try:
                # Try to get current agent from multiple threads
                agent = manager.get_current_agent()
                results.append(agent.id)
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        if errors:
            print(f"✗ Thread safety test failed: {errors}")
            return False
        
        # All threads should get the same agent (whatever is current)
        assert all(r == current_id for r in results), f"Inconsistent results: {results}"
        print(f"✓ Thread safety: {len(results)} threads returned consistent agent '{current_id}'")
        
        return True
    except Exception as e:
        print(f"✗ Thread safety test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_memory_store_thread_safety():
    """Test thread safety of AgentAwareMemoryStore."""
    print("\nTesting AgentAwareMemoryStore thread safety...")
    
    try:
        import threading
        import time
        from myagent.agent.manager import get_agent_manager
        from myagent.memory.agent_store import AgentAwareMemoryStore
        
        manager = get_agent_manager()
        store = AgentAwareMemoryStore(manager)
        
        errors = []
        success_count = [0]  # Use list for mutable reference
        
        def writer_worker():
            try:
                for i in range(5):
                    store.add(
                        content=f"Thread test memory {threading.current_thread().name} #{i}",
                        memory_type="fact",
                        source="thread_test"
                    )
                    success_count[0] += 1
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Write error: {e}")
        
        def reader_worker():
            try:
                for _ in range(5):
                    store.search("thread test", top_k=3)
                    success_count[0] += 1
                    time.sleep(0.01)
            except Exception as e:
                errors.append(f"Read error: {e}")
        
        # Start mix of readers and writers
        threads = []
        for i in range(3):
            threads.append(threading.Thread(target=writer_worker, name=f"Writer-{i}"))
            threads.append(threading.Thread(target=reader_worker, name=f"Reader-{i}"))
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        if errors:
            print(f"✗ Memory store thread safety test failed: {errors}")
            return False
        
        print(f"✓ Memory store thread safety: {success_count[0]} operations succeeded")
        return True
    except Exception as e:
        print(f"✗ Memory store thread safety test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("MyAgent Basic Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_skill_parsing,
        test_memory_data_model,
        test_agent_manager,
        test_thread_safety,
        test_memory_store_thread_safety,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test crashed: {e}")
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
