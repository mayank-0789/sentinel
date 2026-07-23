import yaml
from dataclasses import dataclass
from sentinel.models import Hypothesis, Decision, DecisionMode, PolicyRule

@dataclass
class Policy:
    rules: list

    def _rule_for(self, action_type: str):
        return next((r for r in self.rules if r.action_type == action_type), None)

    def decide(self, hypothesis: Hypothesis, blast_radius: int) -> Decision:
        action = hypothesis.proposed_action
        rule = self._rule_for(action.type.value)
        if rule is None or action.target not in rule.allowed_targets:
            return Decision(DecisionMode.ESCALATE, action, rule.id if rule else "",
                            "no matching rule or target not allowed")
        if (rule.requires_approval or blast_radius > rule.max_blast_radius
                or hypothesis.confidence < rule.auto_execute_if_confidence_gte):
            return Decision(DecisionMode.APPROVE, action, rule.id,
                            f"approval: conf={hypothesis.confidence} blast={blast_radius}")
        return Decision(DecisionMode.AUTO, action, rule.id,
                        f"auto: conf={hypothesis.confidence} within guards")

def load_policy(path: str) -> Policy:
    data = yaml.safe_load(open(path))
    return Policy([PolicyRule(**r) for r in data["rules"]])
