from datetime import datetime
from sentinel.reasoner import hypothesize
from sentinel.models import Incident, Window, IncidentStatus, Evidence, ActionType

class FakeBlock:
    type = "tool_use"; name = "propose_remediation"
    input = {"root_cause": "cart flag failure", "rationale": "5xx from cartservice",
             "action_type": "flag", "target": "cartServiceFailure",
             "params": {"variant": "off"}, "confidence": 0.92}
class FakeMsg:
    content = [FakeBlock()]
class FakeClient:
    class messages:
        @staticmethod
        def create(**kw): return FakeMsg()

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)), IncidentStatus.INVESTIGATING)

def test_hypothesize_parses_tool_call():
    h = hypothesize(_inc(), Evidence(summary="cart 5xx spike"), FakeClient(), "claude-sonnet-5")
    assert h.proposed_action.type is ActionType.FLAG
    assert h.proposed_action.target == "cartServiceFailure"
    assert h.confidence == 0.92
