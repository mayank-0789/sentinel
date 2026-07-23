import time
from datetime import datetime, timezone
from sentinel.models import Incident, RemediationResult, VerificationResult

def verify(incident: Incident, remediation: RemediationResult, backend, baseline: float,
           timeout_s: int = 90, poll_s: int = 10, sleep=time.sleep) -> VerificationResult:
    w = incident.window
    before = backend.get_metric(incident.service, incident.signal, w.start, w.end)
    after = before
    elapsed = 0
    while elapsed < timeout_s:
        after = backend.get_metric(incident.service, incident.signal, w.start, w.end)
        if after <= baseline:
            return VerificationResult(True, before, after, datetime.now(timezone.utc))
        sleep(poll_s)
        elapsed += poll_s
    return VerificationResult(False, before, after, datetime.now(timezone.utc))
