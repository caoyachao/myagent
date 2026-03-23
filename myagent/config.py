"""Configuration management for MyAgent."""

from pathlib import Path
from typing import Optional, Literal

from platformdirs import user_data_dir, user_config_dir
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ArchiveConfig(BaseSettings):
    """Memory archiving configuration."""
    
    # Tier thresholds (days)
    hot_days: int = 30          # Active memory days
    warm_days: int = 90         # Warm memory days
    
    # Activity score thresholds (0-1 scale)
    hot_activity_threshold: float = 0.5      # Minimum activity score for hot tier
    warm_activity_threshold: float = 0.2     # Minimum activity score for warm tier
    
    # Capacity thresholds
    max_hot_memories: int = 1000       # Max active memories
    max_warm_memories: int = 5000      # Max warm memories
    
    # Compression strategy
    compression_strategy: Literal["summary", "merge", "dedup"] = "summary"
    
    # Auto archiving
    auto_archive_enabled: bool = True
    auto_archive_interval_hours: int = 24
    
    # Archive storage
    archive_format: Literal["jsonl", "sqlite"] = "jsonl"
    compression_level: int = 6  # gzip compression level
    
    @field_validator('compression_level')
    @classmethod
    def validate_compression_level(cls, v: int) -> int:
        if not 1 <= v <= 9:
            return 6
        return v


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_prefix="MYAGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    # Data directories
    data_dir: Path = Field(default_factory=lambda: Path(user_data_dir("myagent", "myagent")))
    config_dir: Path = Field(default_factory=lambda: Path(user_config_dir("myagent", "myagent")))
    
    # Memory settings
    memory_db_path: Optional[Path] = None
    chroma_path: Optional[Path] = None
    embedding_model: str = "BAAI/bge-small-zh-v1.5"  # ~100MB, good for Chinese
    embedding_device: str = "cpu"
    max_memories_per_query: int = 10
    memory_score_threshold: float = 0.35
    
    # Skill settings
    skills_dir: Optional[Path] = None
    auto_reload_skills: bool = True
    
    # MCP settings
    mcp_server_name: str = "myagent"
    
    # Logging
    log_level: str = "INFO"
    
    # Archive settings (nested)
    archive: ArchiveConfig = Field(default_factory=ArchiveConfig)
    
    def model_post_init(self, __context):
        """Initialize derived paths."""
        if self.memory_db_path is None:
            self.memory_db_path = self.data_dir / "memories.db"
        if self.chroma_path is None:
            self.chroma_path = self.data_dir / "chroma"
        if self.skills_dir is None:
            self.skills_dir = self.config_dir / "skills"
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    def get_archive_dir(self, agent_id: str) -> Path:
        """Get archive directory for an agent."""
        archive_dir = self.data_dir / "agents" / f"agent-{agent_id}" / "archives"
        archive_dir.mkdir(parents=True, exist_ok=True)
        return archive_dir


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
