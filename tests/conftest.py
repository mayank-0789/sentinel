# tests/conftest.py — shared fixtures
import os, pytest
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SIGNOZ_URL", "http://signoz:8080")
    monkeypatch.setenv("SIGNOZ_QUERY_API_URL", "http://signoz:8080/api/v3")
    monkeypatch.setenv("MCP_URL", "http://mcp:8000")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("FLAGD_CONFIG_PATH", "/tmp/flagd.json")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://signoz:4317")
