from datetime import datetime, timedelta, timezone
from sentinel.models import Incident, Window, IncidentStatus

LOOKBACK = timedelta(minutes=5)

# TODO(day1-findings): confirm SigNoz webhook field paths against a real fired alert

def to_incident(payload: dict, now: datetime) -> Incident:
    alert = payload["alerts"][0]
    labels = alert.get("labels", {})
    fire = alert.get("startsAt")
    end = datetime.fromisoformat(fire.replace("Z", "+00:00")) if fire else now
    return Incident(
        id=alert.get("fingerprint") or labels.get("alertname", "unknown"),
        source_alert=payload,
        service=labels.get("service_name", "unknown"),
        signal=labels.get("signal", "error_rate"),
        severity=labels.get("severity", "warning"),
        window=Window(end - LOOKBACK, end),
        status=IncidentStatus.DETECTED,
    )
