import json
from datetime import datetime, timezone
from sentinel.models import Action, ActionType, RemediationResult

class FlagActuator:
    type = ActionType.FLAG
    def __init__(self, flagd_config_path: str):
        self.path = flagd_config_path
    def apply(self, action: Action) -> RemediationResult:
        variant = action.params.get("variant", "off")
        now = datetime.now(timezone.utc)
        try:
            cfg = json.load(open(self.path))
            cfg["flags"][action.target]["defaultVariant"] = variant
            json.dump(cfg, open(self.path, "w"), indent=2)
            return RemediationResult(action, now, True, f"{action.target} -> {variant}")
        except (KeyError, OSError, ValueError) as e:
            return RemediationResult(action, now, False, f"flag apply failed: {e}")
