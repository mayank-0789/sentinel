import json
from sentinel.models import Action, ActionType
from sentinel.actuators import ActuatorRegistry
from sentinel.actuators.flag import FlagActuator

def test_flag_actuator_sets_variant_off(tmp_path):
    cfg = tmp_path / "flagd.json"
    cfg.write_text(json.dumps({"flags": {"cartServiceFailure": {"defaultVariant": "on",
        "variants": {"on": True, "off": False}}}}))
    res = FlagActuator(str(cfg)).apply(Action(ActionType.FLAG, "cartServiceFailure", {}))
    assert res.ok is True
    assert json.loads(cfg.read_text())["flags"]["cartServiceFailure"]["defaultVariant"] == "off"

def test_registry_dispatches_by_type(tmp_path):
    cfg = tmp_path / "flagd.json"
    cfg.write_text(json.dumps({"flags": {}}))
    reg = ActuatorRegistry()
    reg.register(FlagActuator(str(cfg)))
    assert reg.get(ActionType.FLAG).type is ActionType.FLAG
