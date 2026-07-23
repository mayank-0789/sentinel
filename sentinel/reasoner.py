from sentinel.models import Incident, Evidence, Hypothesis, Action, ActionType

TOOL = {
    "name": "propose_remediation",
    "description": "Return the root cause and a single safe remediation action.",
    "input_schema": {
        "type": "object",
        "properties": {
            "root_cause": {"type": "string"},
            "rationale": {"type": "string"},
            "action_type": {"type": "string", "enum": ["flag", "restart", "scale"]},
            "target": {"type": "string"},
            "params": {"type": "object"},
            "confidence": {"type": "number"},
        },
        "required": ["root_cause", "rationale", "action_type", "target", "confidence"],
    },
}
SYSTEM = ("You are Sentinel, an SRE copilot. Given a SigNoz incident and correlated evidence, "
          "identify the single most likely root cause and propose ONE safe remediation. "
          "Prefer disabling a faulty feature flag when the evidence points to one. "
          "Call propose_remediation with a calibrated confidence.")

def hypothesize(incident: Incident, evidence: Evidence, client, model: str) -> Hypothesis:
    user = (f"Incident: {incident.service} {incident.signal} severity={incident.severity}\n"
            f"Evidence summary: {evidence.summary}\n"
            f"Metrics: {evidence.metrics}\nTopology: {evidence.topology}\n"
            f"Sample traces: {evidence.traces[:5]}\nSample logs: {evidence.logs[:5]}")
    msg = client.messages.create(model=model, max_tokens=2048, system=SYSTEM,
                                 tools=[TOOL], tool_choice={"type": "tool", "name": "propose_remediation"},
                                 messages=[{"role": "user", "content": user}])
    block = next(b for b in msg.content if getattr(b, "type", None) == "tool_use")
    d = block.input
    action = Action(ActionType(d["action_type"]), d["target"], d.get("params", {}))
    return Hypothesis(d["root_cause"], d["rationale"], action, float(d["confidence"]))
