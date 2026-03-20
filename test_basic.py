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
        
        from myagent.memory.store import MemoryStore
        print("✓ memory.store")
        
        from myagent.skills.base import Skill, SkillInfo, parse_skill_md
        print("✓ skills.base")
        
        from myagent.skills.registry import SkillRegistry
        print("✓ skills.registry")
        
        from myagent.tools.registry import ToolRegistry, register_tool
        print("✓ tools.registry")
        
        from myagent.tools.memory_tools import recall_memory, save_memory
        print("✓ tools.memory_tools")
        
        from myagent.prompt.assembler import PromptAssembler
        print("✓ prompt.assembler")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
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


def test_memory_store():
    """Test memory store (requires dependencies)."""
    print("\nTesting memory store...")
    
    try:
        import sentence_transformers
        import chromadb
    except ImportError:
        print("⚠ Skipping (dependencies not installed)")
        return True
    
    from myagent.memory.store import MemoryStore
    
    try:
        store = MemoryStore()
        
        # Add a memory
        mid = store.add(
            content="Test memory content",
            memory_type="fact",
            source="test"
        )
        print(f"✓ Added memory: {mid}")
        
        # Retrieve it
        mem = store.get(mid)
        assert mem is not None
        assert mem.content == "Test memory content"
        print("✓ Retrieved memory")
        
        # Search
        results = store.search("test memory")
        assert len(results) > 0
        print(f"✓ Search returned {len(results)} results")
        
        # Cleanup
        store.delete(mid)
        print("✓ Deleted memory")
        
        return True
    except Exception as e:
        print(f"✗ Memory store test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 50)
    print("MyAgent Basic Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_skill_parsing,
        test_memory_store,
    ]
    
    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
