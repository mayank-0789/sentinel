from sentinel.policy import load_policy
from sentinel.models import Hypothesis, Action, ActionType, DecisionMode

RULES = "policies/rules.yaml"

def _hyp(atype, target, conf):
    return Hypothesis("rc", "why", Action(atype, target, {}), conf)

def test_low_risk_high_confidence_auto_heals():
    d = load_policy(RULES).decide(_hyp(ActionType.FLAG, "cartServiceFailure", 0.95), blast_radius=1)
    assert d.mode is DecisionMode.AUTO
    assert d.policy_rule_id

def test_blast_radius_guard_forces_approval():
    hyp = _hyp(ActionType.RESTART, "cartservice", 0.95)
    policy = load_policy(RULES)
    assert policy.decide(hyp, blast_radius=1).mode is DecisionMode.AUTO
    assert policy.decide(hyp, blast_radius=2).mode is DecisionMode.APPROVE

def test_no_rule_for_action_escalates():
    d = load_policy(RULES).decide(_hyp(ActionType.ROLLBACK, "anything", 0.95), blast_radius=1)
    assert d.mode is DecisionMode.ESCALATE
    assert d.policy_rule_id == ""

def test_low_confidence_needs_approval():
    d = load_policy(RULES).decide(_hyp(ActionType.FLAG, "cartServiceFailure", 0.4), blast_radius=1)
    assert d.mode is DecisionMode.APPROVE

def test_unknown_target_escalates():
    d = load_policy(RULES).decide(_hyp(ActionType.FLAG, "notARealTarget", 0.95), blast_radius=1)
    assert d.mode is DecisionMode.ESCALATE
