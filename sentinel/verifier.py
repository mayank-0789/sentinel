import time
from datetime import datetime, timezone
from sentinel.models import Incident, RemediationResult, VerificationResult

def verify(incident: Incident, remediation: RemediationResult, backend, baseline: float,
           timeout_s: int = 90, poll_s: int = 10, sleep=time.sleep, now=None) -> VerificationResult:
    if now is None:
        now = lambda: datetime.now(timezone.utc)
    window_len = incident.window.end - incident.window.start

    # each call builds a fresh window ending "now" so we observe recovery, not the same past slice
    def _window():
        end = now()
        return end - window_len, end

    start, end = _window()
    before = backend.get_metric(incident.service, incident.signal, start, end)
    after = before
    elapsed = 0
    while elapsed < timeout_s:
        start, end = _window()
        after = backend.get_metric(incident.service, incident.signal, start, end)
        if after <= baseline:
            return VerificationResult(True, before, after, now())
        sleep(poll_s)
        elapsed += poll_s
    return VerificationResult(False, before, after, now())
