from datetime import datetime
from sentinel.audit import AuditStore
from sentinel.models import (Incident, Window, IncidentStatus, Hypothesis,
                             Action, ActionType, Decision, DecisionMode)

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)),
                    IncidentStatus.DETECTED)

def test_record_then_get(tmp_path):
    store = AuditStore(str(tmp_path / "a.db"))
    store.record(_inc())
    rec = store.get("i1")
    assert rec["service"] == "cartservice"
    assert rec["status"] == "DETECTED"

def test_record_upserts_decision(tmp_path):
    store = AuditStore(str(tmp_path / "a.db"))
    inc = _inc()
    store.record(inc)
    store.record(inc, decision=Decision(DecisionMode.AUTO,
        Action(ActionType.FLAG, "cartServiceFailure", {}), "flag-off", "ok"))
    assert store.get("i1")["decision"]["mode"] == "auto"
