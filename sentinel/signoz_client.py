# sentinel/signoz_client.py — the isolation seam: one interface, two backends (spec §5.3)
from typing import Protocol
from datetime import datetime
import httpx

class SignozBackend(Protocol):
    def get_metric(self, service: str, signal: str, start: datetime, end: datetime) -> float: ...
    def get_traces(self, service: str, start: datetime, end: datetime, limit: int = 20) -> list: ...
    def get_logs(self, service: str, start: datetime, end: datetime, limit: int = 50) -> list: ...
    def get_topology(self) -> dict: ...

# TODO(day1-findings): confirm exact Query API request shape against live SigNoz
def _metric_query_payload(service: str, signal: str, start: datetime, end: datetime) -> dict:
    return {
        "start": int(start.timestamp() * 1000),
        "end": int(end.timestamp() * 1000),
        "compositeQuery": {
            "queryType": "builder",
            "builderQueries": {
                "A": {"dataSource": "metrics", "aggregateAttribute": signal,
                      "filters": {"items": [{"key": "service.name", "value": service, "op": "="}]}}
            },
        },
    }

# TODO(day1-findings): confirm exact Query API request shape against live SigNoz
def _trace_query_payload(service: str, start: datetime, end: datetime, limit: int) -> dict:
    return {
        "start": int(start.timestamp() * 1000),
        "end": int(end.timestamp() * 1000),
        "compositeQuery": {
            "queryType": "builder",
            "builderQueries": {
                "A": {"dataSource": "traces", "limit": limit,
                      "filters": {"items": [{"key": "service.name", "value": service, "op": "="}]}}
            },
        },
    }

# TODO(day1-findings): confirm exact Query API request shape against live SigNoz
def _log_query_payload(service: str, start: datetime, end: datetime, limit: int) -> dict:
    return {
        "start": int(start.timestamp() * 1000),
        "end": int(end.timestamp() * 1000),
        "compositeQuery": {
            "queryType": "builder",
            "builderQueries": {
                "A": {"dataSource": "logs", "limit": limit,
                      "filters": {"items": [{"key": "service.name", "value": service, "op": "="}]}}
            },
        },
    }

class QueryApiBackend:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def _query_range(self, payload: dict) -> dict:
        r = httpx.post(f"{self.base}/query_range", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_metric(self, service, signal, start, end) -> float:
        payload = _metric_query_payload(service, signal, start, end)
        data = self._query_range(payload)
        series = data["data"]["result"][0]["series"][0]["values"]
        return float(series[-1][1])

    def get_traces(self, service, start, end, limit=20) -> list:
        return self._query_range(_trace_query_payload(service, start, end, limit)) \
            .get("data", {}).get("result", [])

    def get_logs(self, service, start, end, limit=50) -> list:
        return self._query_range(_log_query_payload(service, start, end, limit)) \
            .get("data", {}).get("result", [])

    def get_topology(self) -> dict:
        r = httpx.get(f"{self.base}/service_map", timeout=30)  # endpoint per findings
        return r.json() if r.status_code == 200 else {}

class McpBackend:
    # TODO(day1-findings): fill from live MCP catalog (Task 1 step 3)
    TOOL_METRIC = "..."
    TOOL_TRACES = "..."
    TOOL_LOGS = "..."
    TOOL_TOPOLOGY = "..."

    def __init__(self, mcp_url: str):
        self.url = mcp_url

    def get_metric(self, service: str, signal: str, start: datetime, end: datetime) -> float:
        from mcp.client.session import ClientSession  # noqa: F401 (lazy: mcp SDK not finalized)
        raise NotImplementedError("McpBackend pending live SigNoz MCP reconciliation")

    def get_traces(self, service: str, start: datetime, end: datetime, limit: int = 20) -> list:
        from mcp.client.session import ClientSession  # noqa: F401
        raise NotImplementedError("McpBackend pending live SigNoz MCP reconciliation")

    def get_logs(self, service: str, start: datetime, end: datetime, limit: int = 50) -> list:
        from mcp.client.session import ClientSession  # noqa: F401
        raise NotImplementedError("McpBackend pending live SigNoz MCP reconciliation")

    def get_topology(self) -> dict:
        from mcp.client.session import ClientSession  # noqa: F401
        raise NotImplementedError("McpBackend pending live SigNoz MCP reconciliation")

def get_backend(settings) -> SignozBackend:
    if settings.evidence_backend == "query_api":
        return QueryApiBackend(settings.signoz_query_api_url)
    return McpBackend(settings.mcp_url)
