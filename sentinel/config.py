from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    signoz_url: str
    signoz_query_api_url: str
    mcp_url: str
    anthropic_api_key: str
    anthropic_model: str = "claude-opus-4-8"
    evidence_backend: str = "mcp"          # "mcp" | "query_api"
    flagd_config_path: str
    audit_db_path: str = "sentinel.db"
    otlp_endpoint: str

@lru_cache
def get_settings() -> Settings:
    return Settings()
