from datetime import datetime, timezone
from sentinel.verifier import verify
from sentinel.models import (Incident, Window, IncidentStatus, Action, ActionType, RemediationResult)

class SeqBackend:
    def __init__(self, seq): self.seq = list(seq)
    def get_metric(self, *a): return self.seq.pop(0)

def _rem():
    return RemediationResult(Action(ActionType.FLAG, "cartServiceFailure", {}),
                             datetime.now(timezone.utc), True, "ok")
def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)), IncidentStatus.VERIFYING)

def test_recovers_when_metric_drops_to_baseline():
    r = verify(_inc(), _rem(), SeqBackend([0.4, 0.2, 0.0]), baseline=0.05,
               timeout_s=60, poll_s=1, sleep=lambda s: None)
    assert r.recovered is True
    assert r.metric_after == 0.0

def test_times_out_when_metric_stays_high():
    r = verify(_inc(), _rem(), SeqBackend([0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]),
               baseline=0.05, timeout_s=3, poll_s=1, sleep=lambda s: None)
    assert r.recovered is False
