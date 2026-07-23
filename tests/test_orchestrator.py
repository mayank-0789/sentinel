from datetime import datetime, timezone
from sentinel.orchestrator import Orchestrator
from sentinel.policy import load_policy
from sentinel.actuators import ActuatorRegistry
from sentinel.actuators.flag import FlagActuator
from sentinel.audit import AuditStore
from sentinel.models import (Incident, Window, IncidentStatus, ActionType)

class Backend:  # healthy metric so verify() recovers immediately
    def get_metric(self,*a): return 0.0
    def get_traces(self,*a,**k): return []
    def get_logs(self,*a,**k): return []
    def get_topology(self): return {"cartservice": ["frontend"]}

def make_client(conf):
    class B: type="tool_use"; name="propose_remediation"; input={
        "root_cause":"cart","rationale":"5xx","action_type":"flag",
        "target":"cartServiceFailure","params":{"variant":"off"},"confidence":conf}
    class M: content=[B()]
    class C:
        class messages:
            @staticmethod
            def create(**kw): return M()
    return C()

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10,tzinfo=timezone.utc),
                           datetime(2026,7,23,10,5,tzinfo=timezone.utc)), IncidentStatus.DETECTED)

def _orch(client, cfg, flag_path):
    reg = ActuatorRegistry(); reg.register(FlagActuator(flag_path))
    return Orchestrator(Backend(), client, load_policy("policies/rules.yaml"), reg,
                        AuditStore(cfg), "claude-sonnet-5",
                        baseline_fn=lambda inc: 0.05)

def test_high_confidence_auto_heals_to_resolved(tmp_path):
    import json; fp = tmp_path/"flagd.json"
    fp.write_text(json.dumps({"flags":{"cartServiceFailure":{"defaultVariant":"on","variants":{"on":True,"off":False}}}}))
    o = _orch(make_client(0.95), str(tmp_path/"a.db"), str(fp))
    out = o.handle(_inc())
    assert out.status is IncidentStatus.RESOLVED

def test_low_confidence_awaits_then_approve_resolves(tmp_path):
    import json; fp = tmp_path/"flagd.json"
    fp.write_text(json.dumps({"flags":{"cartServiceFailure":{"defaultVariant":"on","variants":{"on":True,"off":False}}}}))
    o = _orch(make_client(0.4), str(tmp_path/"a.db"), str(fp))
    out = o.handle(_inc())
    assert out.status is IncidentStatus.AWAITING_APPROVAL
    resolved = o.approve("i1")
    assert resolved.status is IncidentStatus.RESOLVED

def test_stage_failure_marks_incident_failed(tmp_path):
    class BrokenClient:
        class messages:
            @staticmethod
            def create(**kw): raise RuntimeError("no tool_use in response")
    o = _orch(BrokenClient(), str(tmp_path/"a.db"), str(tmp_path/"flagd.json"))
    out = o.handle(_inc())
    assert out.status is IncidentStatus.FAILED
    assert o.audit.get("i1")["status"] == "FAILED"
