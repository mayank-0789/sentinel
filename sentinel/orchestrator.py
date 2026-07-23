from sentinel import evidence as ev, reasoner, verifier
from sentinel.telemetry import span
from sentinel.models import Incident, IncidentStatus, DecisionMode

class Orchestrator:
    def __init__(self, backend, anthropic_client, policy, registry, audit, model,
                 baseline_fn=lambda inc: 0.05):
        self.backend, self.client, self.policy = backend, anthropic_client, policy
        self.registry, self.audit, self.model = registry, audit, model
        self.baseline_fn = baseline_fn
        self.pending = {}

    def handle(self, incident: Incident) -> Incident:
        try:
            with span("incident"):
                self.audit.record(incident)
                with span("investigate"):
                    incident.status = IncidentStatus.INVESTIGATING
                    evidence = ev.gather(incident, self.backend)
                with span("hypothesize"):
                    hyp = reasoner.hypothesize(incident, evidence, self.client, self.model)
                    incident.status = IncidentStatus.DIAGNOSED
                    self.audit.record(incident, hypothesis=hyp)
                with span("decide"):
                    decision = self.policy.decide(hyp, ev.blast_radius(evidence))
                    self.audit.record(incident, decision=decision)
                if decision.mode is DecisionMode.ESCALATE:
                    incident.status = IncidentStatus.ESCALATED
                    self.audit.record(incident)
                    return incident
                if decision.mode is DecisionMode.APPROVE:
                    incident.status = IncidentStatus.AWAITING_APPROVAL
                    self.pending[incident.id] = (incident, hyp, decision)
                    self.audit.record(incident)
                    return incident
                return self._execute(incident, hyp, decision)
        except Exception as e:
            return self._fail(incident, e)

    def approve(self, incident_id: str) -> Incident:
        incident, hyp, decision = self.pending.pop(incident_id)
        try:
            return self._execute(incident, hyp, decision)
        except Exception as e:
            return self._fail(incident, e)

    def _fail(self, incident: Incident, e: Exception) -> Incident:
        incident.status = IncidentStatus.FAILED
        self.audit.record(incident, error=str(e))
        return incident

    def _execute(self, incident, hyp, decision) -> Incident:
        with span("remediate"):
            incident.status = IncidentStatus.REMEDIATING
            actuator = self.registry.get(decision.action.type)
            remediation = actuator.apply(decision.action)
            self.audit.record(incident, remediation=remediation)
            if not remediation.ok:
                incident.status = IncidentStatus.FAILED
                self.audit.record(incident)
                return incident
        with span("verify"):
            incident.status = IncidentStatus.VERIFYING
            result = verifier.verify(incident, remediation, self.backend,
                                     baseline=self.baseline_fn(incident))
            incident.status = IncidentStatus.RESOLVED if result.recovered else IncidentStatus.FAILED
            self.audit.record(incident, verification=result)
        return incident
