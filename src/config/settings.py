"""
Configuration management using Pydantic settings.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from functools import lru_cache

from pydantic import Field, validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    host: str = Field(default="localhost", env="PG_HOST")
    port: int = Field(default=5432, env="PG_PORT")
    database: str = Field(default="postgres", env="PG_DATABASE")
    user: str = Field(default="postgres", env="PG_USER")
    password: SecretStr = Field(default="", env="PG_PASSWORD")
    pool_size: int = Field(default=10, env="PG_POOL_SIZE")
    max_overflow: int = Field(default=20, env="PG_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, env="PG_POOL_TIMEOUT")
    pool_recycle: int = Field(default=3600, env="PG_POOL_RECYCLE")
    echo: bool = Field(default=False, env="PG_ECHO")

    @property
    def url(self) -> str:
        """Generate database URL."""
        return (
            f"postgresql://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    model_config = SettingsConfigDict(env_prefix="PG_")


class MongoDBSettings(BaseSettings):
    """MongoDB configuration."""

    connection_string: SecretStr = Field(
        default="mongodb://localhost:27017",
        env="MONGODB_CONNECTION_STRING"
    )
    database: str = Field(default="text2sql", env="MONGODB_DATABASE")
    collection: str = Field(default="queries", env="MONGODB_COLLECTION")
    max_pool_size: int = Field(default=50, env="MONGODB_MAX_POOL_SIZE")
    min_pool_size: int = Field(default=10, env="MONGODB_MIN_POOL_SIZE")
    max_idle_time_ms: int = Field(default=120000, env="MONGODB_MAX_IDLE_TIME_MS")

    model_config = SettingsConfigDict(env_prefix="MONGODB_")


class AzureOpenAISettings(BaseSettings):
    """Azure OpenAI configuration."""

    endpoint_url: str = Field(default="", env="ENDPOINT_URL")
    api_key: SecretStr = Field(default="", env="AZURE_OPENAI_API_KEY")
    deployment_name: str = Field(default="gpt-4", env="DEPLOYMENT_NAME")
    api_version: str = Field(default="2024-12-01-preview", env="AZURE_API_VERSION")
    temperature: float = Field(default=0.7, env="AZURE_TEMPERATURE")
    max_tokens: int = Field(default=2000, env="AZURE_MAX_TOKENS")
    timeout: int = Field(default=30, env="AZURE_TIMEOUT")
    max_retries: int = Field(default=3, env="AZURE_MAX_RETRIES")

    # Embedding settings
    embedding_endpoint_url: str = Field(default="", env="EMBEDDING_ENDPOINT_URL")
    embedding_model_name: str = Field(
        default="text-embedding-3-small",
        env="EMBEDDING_MODEL_NAME"
    )
    embedding_deployment_name: str = Field(
        default="text-embedding-3-small",
        env="EMBEDDING_DEPLOYMENT_NAME"
    )
    embedding_api_version: str = Field(
        default="2024-12-01-preview",
        env="EMBEDDING_API_VERSION"
    )

    @validator("endpoint_url", "embedding_endpoint_url")
    def validate_endpoint(cls, v):
        """Ensure endpoint URL is properly formatted."""
        if v and not v.startswith("http"):
            raise ValueError("Endpoint URL must start with http or https")
        return v.rstrip("/")  # Remove trailing slash

    model_config = SettingsConfigDict(env_prefix="")


class AzureSearchSettings(BaseSettings):
    """Azure AI Search configuration."""

    endpoint: str = Field(default="", env="AZURE_SEARCH_ENDPOINT")
    key: SecretStr = Field(default="", env="AZURE_SEARCH_KEY")
    index_name: str = Field(default="text2sql", env="AZURE_SEARCH_INDEX")
    api_version: str = Field(default="2023-11-01", env="AZURE_SEARCH_API_VERSION")
    top_k: int = Field(default=10, env="AZURE_SEARCH_TOP_K")
    semantic_config: Optional[str] = Field(default=None, env="AZURE_SEARCH_SEMANTIC_CONFIG")

    model_config = SettingsConfigDict(env_prefix="AZURE_SEARCH_")


class ApplicationSettings(BaseSettings):
    """Application-level configuration."""

    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="text", env="LOG_FORMAT")
    log_dir: Path = Field(default=Path("logs"), env="LOG_DIR")

    # Cache
    cache_ttl: int = Field(default=3600, env="CACHE_TTL")
    cache_backend: str = Field(default="memory", env="CACHE_BACKEND")
    cache_redis_url: Optional[str] = Field(default=None, env="CACHE_REDIS_URL")

    # Retry
    retry_max_attempts: int = Field(default=3, env="RETRY_MAX_ATTEMPTS")
    retry_backoff_factor: float = Field(default=2.0, env="RETRY_BACKOFF_FACTOR")

    # Request
    request_timeout: int = Field(default=30, env="REQUEST_TIMEOUT")
    batch_size: int = Field(default=10, env="BATCH_SIZE")

    # Performance
    max_workers: int = Field(default=4, env="MAX_WORKERS")
    async_enabled: bool = Field(default=True, env="ASYNC_ENABLED")

    @validator("environment")
    def validate_environment(cls, v):
        """Validate environment value."""
        valid_envs = ["development", "staging", "production"]
        if v not in valid_envs:
            raise ValueError(f"Environment must be one of: {valid_envs}")
        return v

    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    model_config = SettingsConfigDict(env_prefix="")


class LangGraphSettings(BaseSettings):
    """LangGraph workflow configuration."""

    max_steps: int = Field(default=10, env="WORKFLOW_MAX_STEPS")
    parallel_execution: bool = Field(default=True, env="WORKFLOW_PARALLEL_EXECUTION")
    state_persistence: bool = Field(default=True, env="STATE_PERSISTENCE")
    checkpoint_dir: Path = Field(default=Path(".checkpoints"), env="CHECKPOINT_DIR")
    enable_tracing: bool = Field(default=True, env="ENABLE_TRACING")
    trace_dir: Path = Field(default=Path(".traces"), env="TRACE_DIR")

    model_config = SettingsConfigDict(env_prefix="WORKFLOW_")


class Settings(BaseSettings):
    """Main settings class combining all configuration sections."""

    # Sub-settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    mongodb: MongoDBSettings = Field(default_factory=MongoDBSettings)
    azure_openai: AzureOpenAISettings = Field(default_factory=AzureOpenAISettings)
    azure_search: AzureSearchSettings = Field(default_factory=AzureSearchSettings)
    app: ApplicationSettings = Field(default_factory=ApplicationSettings)
    langgraph: LangGraphSettings = Field(default_factory=LangGraphSettings)

    # Project paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent / "data")

    def __init__(self, **kwargs):
        """Initialize settings with environment-specific overrides."""
        super().__init__(**kwargs)

        # Load environment-specific settings
        env = self.app.environment
        env_file = Path(f".env.{env}")
        if env_file.exists():
            load_dotenv(env_file, override=True)
            # Reload sub-settings with new environment variables
            self.database = DatabaseSettings()
            self.mongodb = MongoDBSettings()
            self.azure_openai = AzureOpenAISettings()
            self.azure_search = AzureSearchSettings()
            self.app = ApplicationSettings()
            self.langgraph = LangGraphSettings()

    def validate_required_settings(self):
        """Validate that all required settings are configured."""
        errors = []

        # Check database settings
        if not self.database.host:
            errors.append("PostgreSQL host is not configured")
        if not self.database.password.get_secret_value():
            errors.append("PostgreSQL password is not configured")

        # Check Azure OpenAI settings
        if not self.azure_openai.endpoint_url:
            errors.append("Azure OpenAI endpoint URL is not configured")
        if not self.azure_openai.api_key.get_secret_value():
            errors.append("Azure OpenAI API key is not configured")

        # Check MongoDB settings
        if not self.mongodb.connection_string.get_secret_value():
            errors.append("MongoDB connection string is not configured")

        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")

    def get_env_config(self) -> Dict[str, Any]:
        """Get environment-specific configuration."""
        env_configs = {
            "development": {
                "debug": True,
                "testing": True,
                "hot_reload": True,
            },
            "staging": {
                "debug": False,
                "testing": True,
                "hot_reload": False,
            },
            "production": {
                "debug": False,
                "testing": False,
                "hot_reload": False,
            }
        }
        return env_configs.get(self.app.environment, {})

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app.environment == "production"

    def to_dict(self, include_secrets: bool = False) -> Dict[str, Any]:
        """
        Export settings as dictionary.

        Args:
            include_secrets: Whether to include secret values

        Returns:
            Dictionary of settings
        """
        def process_value(v):
            if isinstance(v, SecretStr):
                return v.get_secret_value() if include_secrets else "***"
            elif isinstance(v, Path):
                return str(v)
            elif isinstance(v, BaseSettings):
                return {
                    k: process_value(getattr(v, k))
                    for k in v.model_fields.keys()
                }
            return v

        return {
            "database": process_value(self.database),
            "mongodb": process_value(self.mongodb),
            "azure_openai": process_value(self.azure_openai),
            "azure_search": process_value(self.azure_search),
            "app": process_value(self.app),
            "langgraph": process_value(self.langgraph),
            "project_root": str(self.project_root),
            "data_dir": str(self.data_dir),
        }

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings instance
    """
    settings = Settings()
    # Only validate in non-development environments
    if not settings.is_development:
        settings.validate_required_settings()
    return settings


# Convenience function for accessing settings
def get_config() -> Settings:
    """Alias for get_settings()."""
    return get_settings()