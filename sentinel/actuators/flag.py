import json
import os
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
            with open(self.path) as f:
                cfg = json.load(f)
            cfg["flags"][action.target]["defaultVariant"] = variant
            tmp_path = self.path + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump(cfg, f, indent=2)
            os.replace(tmp_path, self.path)
            return RemediationResult(action, now, True, f"{action.target} -> {variant}")
        except Exception as e:
            return RemediationResult(action, now, False, f"flag apply failed: {e}")
