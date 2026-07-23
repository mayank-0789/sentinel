from sentinel.config import get_settings
def test_settings_load_from_env():
    s = get_settings()
    assert s.mcp_url == "http://mcp:8000"
    assert s.anthropic_model == "claude-opus-4-8"
    assert s.evidence_backend == "query_api"
