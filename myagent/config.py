"""Configuration management for MyAgent."""

from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir, user_config_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
