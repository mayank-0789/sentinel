from datetime import datetime
from sentinel.evidence import gather, blast_radius
from sentinel.models import Incident, Window, IncidentStatus

class FakeBackend:
    def get_metric(self, *a): return 0.42
    def get_traces(self, *a, **k): return [{"name": "POST /checkout", "status": "ERROR"}]
    def get_logs(self, *a, **k): return [{"body": "cart error"}]
    def get_topology(self): return {"cartservice": ["checkoutservice", "frontend"]}

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)), IncidentStatus.DETECTED)

def test_gather_populates_all_channels():
    ev = gather(_inc(), FakeBackend())
    assert ev.metrics["error_rate"] == 0.42
    assert ev.traces and ev.logs
    assert "cartservice" in ev.summary

def test_blast_radius_counts_downstream():
    ev = gather(_inc(), FakeBackend())
    assert blast_radius(ev) == 2
