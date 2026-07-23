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

def test_flag_actuator_returns_failure_on_malformed_config(tmp_path):
    cfg = tmp_path / "flagd.json"
    cfg.write_text(json.dumps({"flags": {"cartServiceFailure": "oops"}}))
    res = FlagActuator(str(cfg)).apply(Action(ActionType.FLAG, "cartServiceFailure", {}))
    assert res.ok is False

    missing_cfg = tmp_path / "flagd_missing.json"
    missing_cfg.write_text(json.dumps({"flags": {}}))
    res2 = FlagActuator(str(missing_cfg)).apply(Action(ActionType.FLAG, "cartServiceFailure", {}))
    assert res2.ok is False
