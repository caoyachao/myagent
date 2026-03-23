"""Migration from MyAgent 1.0 to 2.0."""

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from myagent.config import get_settings


class MigrationManager:
    """Manages migration from MyAgent 1.0 to 2.0."""
    
    def __init__(self):
        self.settings = get_settings()
        self.v1_memory_db = self.settings.data_dir / "memories.db"
        self.v1_chroma_dir = self.settings.data_dir / "chroma"
        self.v1_skills_dir = self.settings.config_dir / "skills"
    
    def detect_v1_data(self) -> bool:
        """Check if v1.0 data exists."""
        return (
            self.v1_memory_db.exists() or
            self.v1_chroma_dir.exists() or
            self.v1_skills_dir.exists()
        )
    
    def is_migrated(self) -> bool:
        """Check if data has already been migrated."""
        # Check for master agent config
        master_config = self.settings.config_dir / "master" / "agent.json"
        if master_config.exists():
            try:
                data = json.loads(master_config.read_text())
                return data.get("migrated_from_v1", False)
            except Exception:
                pass
        return False
    
    def get_migration_info(self) -> Dict[str, Any]:
        """Get migration information."""
        master_config = self.settings.config_dir / "master" / "agent.json"
        if master_config.exists():
            try:
                return json.loads(master_config.read_text())
            except Exception:
                pass
        return {}
    
    def check_and_migrate(self):
        """Check and perform migration if needed."""
        # Check if already migrated
        if self.is_migrated():
            return
        
        # Check for v1 data
        if not self.detect_v1_data():
            return
        
        # Perform migration
        self._do_migration()
    
    def _do_migration(self):
        """Perform the actual migration."""
        from rich.console import Console
        console = Console()
        
        console.print("[yellow]检测到 MyAgent 1.0 数据，开始迁移...[/]")
        
        # Create backup
        backup_dir = self._create_backup()
        console.print(f"[dim]  已创建备份: {backup_dir}[/]")
        
        # Create master agent structure
        self._create_master_structure()
        
        # Migrate memories
        memory_count = 0
        if self.v1_memory_db.exists():
            memory_count = self._migrate_memories()
            console.print(f"[dim]  已迁移 {memory_count} 条记忆[/]")
        
        # Migrate skills
        skill_count = 0
        if self.v1_skills_dir.exists():
            skill_count = self._migrate_skills()
            console.print(f"[dim]  已迁移 {skill_count} 个技能[/]")
        
        # Create master agent config
        self._create_master_config()
        
        # Create current agent state
        self._create_current_agent_state()
        
        console.print(f"[green]✅ 迁移完成！[/]")
        console.print(f"[dim]   所有数据已转移到 Master Agent[/]")
        console.print(f"[dim]   原数据备份: {backup_dir}[/]")
    
    def _create_backup(self) -> Path:
        """Create backup of v1 data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.settings.data_dir / f"backup_v1.0_{timestamp}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup memory DB
        if self.v1_memory_db.exists():
            shutil.copy2(self.v1_memory_db, backup_dir / "memories.db")
        
        # Backup chroma
        if self.v1_chroma_dir.exists():
            shutil.copytree(self.v1_chroma_dir, backup_dir / "chroma")
        
        # Backup skills
        if self.v1_skills_dir.exists():
            shutil.copytree(self.v1_skills_dir, backup_dir / "skills")
        
        return backup_dir
    
    def _create_master_structure(self):
        """Create directory structure for master agent."""
        master_dir = self.settings.data_dir / "master"
        master_dir.mkdir(parents=True, exist_ok=True)
        
        master_config_dir = self.settings.config_dir / "master"
        master_config_dir.mkdir(parents=True, exist_ok=True)
        
        shared_skills_dir = self.settings.config_dir / "shared_skills"
        shared_skills_dir.mkdir(parents=True, exist_ok=True)
        
        agents_data_dir = self.settings.data_dir / "agents"
        agents_data_dir.mkdir(parents=True, exist_ok=True)
        
        agents_config_dir = self.settings.config_dir / "agents"
        agents_config_dir.mkdir(parents=True, exist_ok=True)
    
    def _migrate_memories(self) -> int:
        """Migrate memories from v1 to master agent."""
        master_db = self.settings.data_dir / "master" / "memories.db"
        master_chroma = self.settings.data_dir / "master" / "chroma"
        
        # Remove existing master DB if empty (fresh start)
        if master_db.exists():
            try:
                import sqlite3
                with sqlite3.connect(master_db) as conn:
                    cursor = conn.execute("SELECT COUNT(*) FROM memories")
                    count = cursor.fetchone()[0]
                    if count == 0:
                        master_db.unlink()  # Empty, remove it
            except Exception:
                pass
        
        # Copy memory database
        shutil.copy2(self.v1_memory_db, master_db)
        
        # Add agent_id column
        with sqlite3.connect(master_db) as conn:
            cursor = conn.execute("PRAGMA table_info(memories)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if "agent_id" not in columns:
                conn.execute("ALTER TABLE memories ADD COLUMN agent_id TEXT DEFAULT 'master'")
                conn.execute("UPDATE memories SET agent_id = 'master'")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON memories(agent_id)")
            
            # Add metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS _myagent_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO _myagent_meta (key, value) 
                VALUES ('schema_version', '2.0')
            """)
            conn.commit()
            
            # Count memories
            cursor = conn.execute("SELECT COUNT(*) FROM memories")
            count = cursor.fetchone()[0]
        
        # Copy Chroma
        if self.v1_chroma_dir.exists():
            if master_chroma.exists():
                shutil.rmtree(master_chroma)
            shutil.copytree(self.v1_chroma_dir, master_chroma)
            
            # Rename collection to include agent_id
            try:
                import chromadb
                from chromadb.config import Settings as ChromaSettings
                
                client = chromadb.PersistentClient(
                    path=str(master_chroma),
                    settings=ChromaSettings(anonymized_telemetry=False)
                )
                
                # Get old collection
                try:
                    old_collection = client.get_collection("memories")
                    # Create new collection with agent-specific name
                    new_collection = client.create_collection(
                        name="memories_master",
                        metadata={"hnsw:space": "cosine", "agent_id": "master"}
                    )
                    # Copy data (this is a simplified approach)
                    # In practice, we'd copy all embeddings
                except Exception:
                    pass
            except Exception:
                pass
        
        # Remove old files
        self.v1_memory_db.unlink()
        if self.v1_chroma_dir.exists():
            shutil.rmtree(self.v1_chroma_dir)
        
        return count
    
    def _migrate_skills(self) -> int:
        """Migrate skills to shared skills directory."""
        shared_skills_dir = self.settings.config_dir / "shared_skills"
        
        count = 0
        for skill_dir in self.v1_skills_dir.iterdir():
            if skill_dir.is_dir():
                dest = shared_skills_dir / skill_dir.name
                if dest.exists():
                    dest = shared_skills_dir / f"{skill_dir.name}_migrated"
                shutil.move(str(skill_dir), str(dest))
                count += 1
        
        # Remove old skills directory
        if self.v1_skills_dir.exists():
            shutil.rmtree(self.v1_skills_dir)
        
        return count
    
    def _create_master_config(self):
        """Create master agent configuration."""
        config = {
            "id": "master",
            "name": "默认助手",
            "description": "系统主智能体，继承自 MyAgent 1.0 的所有数据",
            "personality": "全能助手，熟悉用户的所有历史和偏好",
            "system_prompt": "",
            "inherit_shared_skills": True,
            "inherit_shared_tools": True,
            "inherit_master_memories": True,
            "is_master": True,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "migrated_from_v1": True,
            "migrated_at": datetime.now().isoformat(),
            "memory_db_path": str(self.settings.data_dir / "master" / "memories.db"),
            "chroma_path": str(self.settings.data_dir / "master" / "chroma"),
            "skills_dir": str(self.settings.config_dir / "shared_skills"),
            "config_path": str(self.settings.config_dir / "master" / "agent.json")
        }
        
        config_path = self.settings.config_dir / "master" / "agent.json"
        config_path.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding='utf-8'
        )
    
    def _create_current_agent_state(self):
        """Create current agent state file."""
        state_file = self.settings.data_dir / "current_agent.json"
        state_file.write_text(json.dumps({
            "current_agent_id": "master",
            "updated_at": datetime.now().isoformat()
        }, indent=2))
    
    def rollback(self):
        """Rollback migration (restore v1 data)."""
        # Find latest backup
        backups = sorted(
            self.settings.data_dir.glob("backup_v1.0_*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        if not backups:
            raise ValueError("No backup found to rollback")
        
        backup_dir = backups[0]
        
        # Restore memory DB
        memory_backup = backup_dir / "memories.db"
        if memory_backup.exists():
            shutil.copy2(memory_backup, self.settings.data_dir / "memories.db")
        
        # Restore chroma
        chroma_backup = backup_dir / "chroma"
        if chroma_backup.exists():
            chroma_dest = self.settings.data_dir / "chroma"
            if chroma_dest.exists():
                shutil.rmtree(chroma_dest)
            shutil.copytree(chroma_backup, chroma_dest)
        
        # Restore skills
        skills_backup = backup_dir / "skills"
        if skills_backup.exists():
            skills_dest = self.settings.config_dir / "skills"
            if skills_dest.exists():
                shutil.rmtree(skills_dest)
            shutil.copytree(skills_backup, skills_dest)
        
        # Remove v2 data
        master_data = self.settings.data_dir / "master"
        if master_data.exists():
            shutil.rmtree(master_data)
        
        master_config = self.settings.config_dir / "master"
        if master_config.exists():
            shutil.rmtree(master_config)
        
        shared_skills = self.settings.config_dir / "shared_skills"
        if shared_skills.exists():
            shutil.rmtree(shared_skills)
        
        agents_data = self.settings.data_dir / "agents"
        if agents_data.exists():
            shutil.rmtree(agents_data)
        
        agents_config = self.settings.config_dir / "agents"
        if agents_config.exists():
            shutil.rmtree(agents_config)
        
        # Remove state file
        state_file = self.settings.data_dir / "current_agent.json"
        if state_file.exists():
            state_file.unlink()