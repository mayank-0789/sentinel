import json, threading
from datetime import datetime, timezone
from sentinel.audit import AuditStore, _enc
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

def test_record_upsert_merges_hypothesis_and_decision(tmp_path):
    store = AuditStore(str(tmp_path / "a.db"))
    inc = _inc()
    hyp = Hypothesis("oom", "memory graph spiked", Action(ActionType.RESTART, "cartservice", {}), 0.9)
    store.record(inc, hypothesis=hyp)
    store.record(inc, decision=Decision(DecisionMode.AUTO,
        Action(ActionType.FLAG, "cartServiceFailure", {}), "flag-off", "ok"))
    rec = store.get("i1")
    assert rec["hypothesis"]["root_cause"] == "oom"
    assert rec["decision"]["mode"] == "auto"

def test_enc_recurses_into_nested_dicts():
    result = _enc({"outer": {"ts": datetime(2026, 7, 23, tzinfo=timezone.utc)}})
    assert result["outer"]["ts"] == "2026-07-23T00:00:00+00:00"

def test_enc_converts_enum_to_value():
    decision = Decision(DecisionMode.AUTO, Action(ActionType.FLAG, "x", {}), "flag-off", "ok")
    enc = _enc(decision)
    json.dumps(enc)
    assert enc["mode"] == "auto"
    assert enc["action"]["type"] == "flag"

def test_audit_store_usable_from_another_thread(tmp_path):
    store = AuditStore(str(tmp_path / "a.db"))
    errors = []

    def worker():
        try:
            store.record(_inc())
            store.get("i1")
        except Exception as e:
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert errors == []
    assert store.get("i1")["service"] == "cartservice"
