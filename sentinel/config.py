from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    signoz_url: str
    signoz_query_api_url: str
    signoz_api_key: str = ""            # SIGNOZ-API-KEY header for the query API (SigNoz → Settings → API Keys)
    mcp_url: str
    anthropic_api_key: str = ""         # empty → reasoner runs in offline stub mode (no spend)
    anthropic_model: str = "claude-opus-4-8"
    evidence_backend: str = "query_api"    # "mcp" | "query_api"
    flagd_config_path: str
    demo_flag: str = "cartFailure"     # stub-reasoner remediation target when running keyless
    audit_db_path: str = "sentinel.db"
    otlp_endpoint: str

@lru_cache
def get_settings() -> Settings:
    return Settings()
