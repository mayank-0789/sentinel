from fastapi.testclient import TestClient
from sentinel.app import build_app
from sentinel.models import Incident, Window, IncidentStatus
from datetime import datetime, timezone

class FakeOrch:
    def __init__(self): self.handled = None
    def handle(self, inc): self.handled = inc; inc.status = IncidentStatus.RESOLVED; return inc
    def approve(self, iid): return Incident(iid, {}, "cartservice","error_rate","critical",
        Window(datetime(2026,7,23,10,tzinfo=timezone.utc),datetime(2026,7,23,10,5,tzinfo=timezone.utc)),
        IncidentStatus.RESOLVED)

PAYLOAD = {"status":"firing","alerts":[{"fingerprint":"abc","labels":
    {"service_name":"cartservice","signal":"error_rate","severity":"critical"},
    "startsAt":"2026-07-23T10:05:00Z"}]}

RESOLVED_PAYLOAD = {"status":"resolved","alerts":[{"fingerprint":"abc","labels":
    {"service_name":"cartservice","signal":"error_rate","severity":"critical"},
    "startsAt":"2026-07-23T10:05:00Z"}]}

def test_webhook_accepts_and_returns_incident_id():
    app = build_app(orchestrator=FakeOrch())
    r = TestClient(app).post("/webhook", json=PAYLOAD)
    assert r.status_code == 202
    assert r.json()["incident_id"] == "abc"

def test_healthz():
    assert TestClient(build_app(orchestrator=FakeOrch())).get("/healthz").status_code == 200

def test_webhook_ignores_resolved():
    orch = FakeOrch()
    r = TestClient(build_app(orchestrator=orch)).post("/webhook", json=RESOLVED_PAYLOAD)
    assert r.status_code == 202
    body = r.json()
    assert body["incident_id"] is None
    assert body["status"] == "ignored"
    assert orch.handled is None

class ApproveOkOrch:
    def approve(self, iid): return Incident(iid, {}, "cartservice","error_rate","critical",
        Window(datetime(2026,7,23,10,tzinfo=timezone.utc),datetime(2026,7,23,10,5,tzinfo=timezone.utc)),
        IncidentStatus.RESOLVED)

class ApproveMissingOrch:
    def approve(self, iid): raise KeyError(iid)

def test_approve_happy_path_returns_incident():
    r = TestClient(build_app(orchestrator=ApproveOkOrch())).post("/incidents/abc/approve")
    assert r.status_code == 200
    assert r.json() == {"incident_id": "abc", "status": "RESOLVED"}

def test_approve_unknown_incident_returns_404():
    r = TestClient(build_app(orchestrator=ApproveMissingOrch())).post("/incidents/nope/approve")
    assert r.status_code == 404

class FakeAudit:
    def __init__(self, record): self._record = record
    def get(self, incident_id): return self._record if incident_id == "abc" else None

class AuditOrch:
    def __init__(self, record): self.audit = FakeAudit(record)

def test_get_incident_returns_audit_record():
    record = {"id": "abc", "status": "RESOLVED"}
    r = TestClient(build_app(orchestrator=AuditOrch(record))).get("/incidents/abc")
    assert r.status_code == 200
    assert r.json() == record

def test_get_incident_missing_returns_404():
    r = TestClient(build_app(orchestrator=AuditOrch({}))).get("/incidents/nope")
    assert r.status_code == 404
