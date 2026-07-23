from datetime import datetime, timezone
from sentinel.detector import to_incident
from sentinel.models import IncidentStatus

PAYLOAD = {
  "status": "firing",
  "alerts": [{
    "fingerprint": "abc123",
    "labels": {"alertname": "cart-error-rate", "service_name": "cartservice",
               "severity": "critical", "signal": "error_rate"},
    "annotations": {"description": "error rate > 5%"},
    "startsAt": "2026-07-23T10:05:00Z"}]
}

def test_to_incident_extracts_core_fields():
    inc = to_incident(PAYLOAD, now=datetime(2026,7,23,10,5,tzinfo=timezone.utc))
    assert inc.service == "cartservice"
    assert inc.signal == "error_rate"
    assert inc.severity == "critical"
    assert inc.status is IncidentStatus.DETECTED
    assert inc.id == "abc123"

def test_window_is_five_minute_lookback():
    inc = to_incident(PAYLOAD, now=datetime(2026,7,23,10,5,tzinfo=timezone.utc))
    assert (inc.window.end - inc.window.start).total_seconds() == 300
