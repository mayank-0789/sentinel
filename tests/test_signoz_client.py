import respx, httpx
from datetime import datetime
from sentinel.signoz_client import QueryApiBackend, get_backend
from sentinel.config import get_settings

@respx.mock
def test_query_api_get_metric_parses_last_value():
    respx.post("http://signoz:8080/api/v3/query_range").mock(return_value=httpx.Response(
        200, json={"data": {"result": [{"series": [{"values": [[1, "0.0"], [2, "0.42"]]}]}]}}))
    v = QueryApiBackend("http://signoz:8080/api/v3").get_metric(
        "cartservice", "error_rate", datetime(2026,7,23,10), datetime(2026,7,23,10,5))
    assert v == 0.42

def test_get_backend_selects_query_api(monkeypatch):
    monkeypatch.setenv("EVIDENCE_BACKEND", "query_api")
    get_settings.cache_clear()
    assert type(get_backend(get_settings())).__name__ == "QueryApiBackend"
