from typing import Protocol
from sentinel.models import Action, ActionType, RemediationResult

class Actuator(Protocol):
    type: ActionType
    def apply(self, action: Action) -> RemediationResult: ...

class ActuatorRegistry:
    def __init__(self):
        self._by_type = {}
    def register(self, actuator: Actuator):
        self._by_type[actuator.type] = actuator
    def get(self, action_type: ActionType) -> Actuator:
        return self._by_type[action_type]
