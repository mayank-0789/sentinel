from datetime import datetime
from sentinel.models import (
    Incident, Window, IncidentStatus, Action, ActionType,
    Hypothesis, Decision, DecisionMode, PolicyRule,
)
def test_incident_defaults_to_detected():
    inc = Incident(id="i1", source_alert={}, service="cartservice",
                   signal="error_rate", severity="critical",
                   window=Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)))
    assert inc.status is IncidentStatus.DETECTED

def test_hypothesis_carries_action():
    h = Hypothesis(root_cause="cart failing", rationale="5xx spike",
                   proposed_action=Action(ActionType.FLAG, "cartServiceFailure", {"value": False}),
                   confidence=0.9)
    assert h.proposed_action.type is ActionType.FLAG
    assert 0.0 <= h.confidence <= 1.0

def test_enums_are_str_serialisable():
    assert DecisionMode.AUTO == "auto"
    assert ActionType.FLAG.value == "flag"
