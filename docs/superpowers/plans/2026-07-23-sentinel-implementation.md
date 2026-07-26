# Sentinel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Sentinel — a policy-gated, self-healing SRE copilot that detects a SigNoz alert, gathers evidence via the SigNoz MCP server + Claude, decides auto-heal vs. human-approval, applies a guarded fix, and verifies recovery — all while tracing itself into SigNoz.

**Architecture:** A Python FastAPI service receives SigNoz alert webhooks and drives an incident state machine through six stages (detect → evidence → reason → policy → actuate → verify). All SigNoz access is hidden behind one `SignozBackend` interface with an MCP primary and a REST Query API fallback, so the MCP-is-beta risk is a config flag, not a rewrite. Reasoning is Claude via the Anthropic API. Everything runs in Docker Compose; SigNoz is deployed via Foundry.

**Tech Stack:** Python 3.11+, FastAPI + uvicorn, `anthropic` SDK, `mcp` SDK (+ `httpx` for Query API fallback), OpenTelemetry SDK (self-tracing), SQLite (audit), PyYAML (policy), Docker Compose, Foundry (`foundryctl`), OpenTelemetry Demo, Playwright (E2E + demo capture), pytest.

## Global Constraints

Copied verbatim from the spec + CLAUDE.md. Every task implicitly includes these.

- **No code committed before 2026-07-20.** (Today is 2026-07-23 — this constraint has passed; all code commits are now allowed and must be dated Jul 20 or later. Pre-Jul-20 commits are planning docs only.)
- **AI assistance MUST be disclosed** in the submission. Non-disclosure = DQ.
- **Ship `casting.yaml` + `casting.yaml.lock`** in the repo (judges re-run via Foundry).
- **SigNoz used deeply** — traces + logs + metrics + dashboards + alerts + MCP + Sentinel's own telemetry.
- **Lean. Simplest thing that works. Ask before adding layers.**
- **Comments minimal — only where the *why* isn't obvious; 1–2 lines max; never stacked/blocked. Use `#` in the Python core, `//` in the Next.js/TS UI. Names + structure carry meaning, not comments.**
- **Human gates (STOP — never do solo):** making the repo public / pushing to a remote; submitting hackathon forms; publishing the blog; spending money/credits beyond free/local tiers; anything irreversible or outward-facing; changing scope/track.
- **Never advance on red.** Evidence before any "it works" claim (`make verify` green).

## Timeline reality (as of 2026-07-23)

Original spec timeline was Jul 20–26 with de-risk on D1. Nothing was built (env not up). Effective build window remaining: **Jul 23, 24, 25**, with **Jul 26 = buffer + submit**. The plan is therefore ordered strictly by demo value: the auto-heal core loop (Scenario 1) end-to-end is the winning MVP and comes first; the human-approval governance path (Scenario 3), extra actuators, and the web UI are stretch and are cut from the bottom if time runs out. **Cut order (last first): Task 20 (UI) → Task 19 (governance path/extra actuators/Scenario 3) → Task 16 dashboard polish.** The dashboard, self-telemetry, README, and disclosed demo video are NOT cuttable — they carry the "Best Use of SigNoz" and "Presentation" criteria.

---

## Locked data model (used by every task)

These are the exact types from spec §7. Tasks below reference these names verbatim — do not rename.

```python
# sentinel/models.py — the single source of shared types
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    INVESTIGATING = "INVESTIGATING"
    DIAGNOSED = "DIAGNOSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    REMEDIATING = "REMEDIATING"
    VERIFYING = "VERIFYING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"

class ActionType(str, Enum):
    FLAG = "flag"
    RESTART = "restart"
    SCALE = "scale"
    ROLLBACK = "rollback"

class DecisionMode(str, Enum):
    AUTO = "auto"
    APPROVE = "approve"
    ESCALATE = "escalate"

@dataclass
class Window:
    start: datetime
    end: datetime

@dataclass
class Incident:
    id: str
    source_alert: dict
    service: str
    signal: str            # e.g. "error_rate" | "p99_latency"
    severity: str
    window: Window
    status: IncidentStatus = IncidentStatus.DETECTED

@dataclass
class Evidence:
    traces: list = field(default_factory=list)
    logs: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    topology: dict = field(default_factory=dict)
    recent_deploys: list = field(default_factory=list)
    summary: str = ""

@dataclass
class Action:
    type: ActionType
    target: str
    params: dict = field(default_factory=dict)

@dataclass
class Hypothesis:
    root_cause: str
    rationale: str
    proposed_action: Action
    confidence: float      # 0..1

@dataclass
class Decision:
    mode: DecisionMode
    action: Action
    policy_rule_id: str
    reason: str

@dataclass
class RemediationResult:
    action: Action
    applied_at: datetime
    ok: bool
    detail: str

@dataclass
class VerificationResult:
    recovered: bool
    metric_before: float
    metric_after: float
    checked_until: datetime

@dataclass
class PolicyRule:
    action_type: str
    risk: str              # "low" | "med" | "high"
    auto_execute_if_confidence_gte: float
    requires_approval: bool
    allowed_targets: list
    id: str = ""
    max_blast_radius: int = 1
```

## File structure

```
sentinel/                          # repo root (git already initialised)
├── casting.yaml                   # Foundry — SigNoz + MCP     (Task 1, committed)
├── casting.yaml.lock              # Foundry lockfile           (Task 1, committed)
├── compose.yaml                   # OTel Demo + Sentinel (+UI) (Task 1)
├── Makefile                       # up / demo / verify / down / e2e (Task 1 seed → Task 17 final)
├── pyproject.toml                 # deps + pytest config       (Task 2)
├── .env.example                   # SIGNOZ_URL, MCP_URL, ANTHROPIC_API_KEY, ... (Task 2)
├── sentinel/
│   ├── __init__.py
│   ├── models.py                  # locked data model above    (Task 3)
│   ├── config.py                  # env-driven Settings         (Task 2)
│   ├── policy.py                  # Hypothesis → Decision       (Task 4)
│   ├── actuators/
│   │   ├── __init__.py            # Actuator protocol + registry (Task 5)
│   │   ├── flag.py                # FlagActuator (MVP)          (Task 5)
│   │   ├── restart.py             # RestartActuator (stretch)   (Task 19)
│   │   └── scale.py               # ScaleActuator (stretch)     (Task 19)
│   ├── audit.py                   # SQLite append-only store    (Task 6)
│   ├── signoz_client.py           # SignozBackend + QueryApi + Mcp (Task 8)
│   ├── evidence.py                # Incident → Evidence         (Task 9)
│   ├── verifier.py                # → VerificationResult        (Task 10)
│   ├── detector.py                # webhook dict → Incident     (Task 11)
│   ├── reasoner.py                # (Incident,Evidence) → Hypothesis (Task 12)
│   ├── telemetry.py               # OTel self-tracing           (Task 13)
│   ├── orchestrator.py            # incident state machine      (Task 14)
│   └── app.py                     # FastAPI webhook + approval  (Task 15)
├── policies/
│   └── rules.yaml                 # policy rules                (Task 4)
├── dashboards/
│   └── sentinel-ops.json          # SigNoz "Sentinel Ops" dash  (Task 16)
├── scenarios/
│   └── flagd_chaos.py             # inject/heal via flagd       (Task 17)
├── ui/                            # Next.js incident feed       (Task 20, stretch)
├── tests/
│   ├── conftest.py                # fixtures + fakes            (Task 2)
│   ├── test_models.py             (Task 3)
│   ├── test_policy.py             (Task 4)
│   ├── test_actuators.py          (Task 5)
│   ├── test_audit.py              (Task 6)
│   ├── test_signoz_client.py      (Task 8)
│   ├── test_evidence.py           (Task 9)
│   ├── test_verifier.py           (Task 10)
│   ├── test_detector.py           (Task 11)
│   ├── test_reasoner.py           (Task 12)
│   ├── test_orchestrator.py       (Task 14)
│   ├── test_app.py                (Task 15)
│   └── e2e/
│       └── test_scenario1.py      (Task 17, Playwright)
└── docs/
    ├── superpowers/specs/2026-07-15-sentinel-sre-copilot-design.md
    ├── superpowers/plans/2026-07-23-sentinel-implementation.md   # this file
    ├── day1-findings.md           # captured de-risk artifact    (Task 1)
    └── decisions-log.md           # running decisions            (all tasks)
```

---

## Phase 0 — Foundation & de-risk (Jul 23, do first)

### Task 1: Stand up the stack and capture the four unknowns

**Files:**
- Create: `compose.yaml`
- Create: `casting.yaml`, `casting.yaml.lock`
- Create: `Makefile` (seed targets `up`/`down`)
- Create: `docs/day1-findings.md` (the artifact later tasks read)
- Create: `docs/decisions-log.md`

**Interfaces:**
- Consumes: nothing.
- Produces: `docs/day1-findings.md` containing, verbatim, **(a)** the SigNoz alert webhook JSON body for one real fired alert, **(b)** the MCP tool catalog (names + params of every tool the SigNoz MCP server exposes on :8000), **(c)** the exact `flagd` flag names for Scenarios 1–3 in the pulled OTel Demo version, **(d)** confirmation of a working Anthropic API key. These are the inputs to Tasks 8/9/11/17.

- [ ] **Step 1: Deploy SigNoz + MCP via Foundry.** Write `casting.yaml` selecting the SigNoz Docker/compose flavor with the **MCP server enabled on :8000** (it is off by default — turn it on explicitly). Run `foundryctl cast` and commit `casting.yaml` + the generated `casting.yaml.lock`.

Run: `foundryctl cast && docker compose ps`
Expected: SigNoz UI reachable at `http://localhost:8080` (or the port Foundry reports); an MCP container listening on `:8000`.

- [ ] **Step 2: Bring up the OTel Demo** in `compose.yaml`, pointed at SigNoz's OTLP endpoint. Confirm the astronomy-shop services and load generator are producing traces/logs/metrics visible in the SigNoz UI.

Run: `docker compose -f compose.yaml up -d && sleep 60`
Expected: SigNoz "Services" page lists ~15 services with live RPS/latency.

- [ ] **Step 3: Enumerate the MCP tool catalog.** Connect an MCP client to `:8000`, list tools, and paste the full tool list (names, descriptions, input schemas) into `docs/day1-findings.md`. Note which map to: metric aggregate, trace search, log search, service topology.

Run: a throwaway script using the `mcp` SDK `list_tools()` against the SigNoz MCP endpoint.
Expected: a concrete list of tool names recorded in the artifact. **If the catalog is thin (no trace/log search), record that — Task 8 will lean on the Query API fallback.**

- [ ] **Step 4: Fire one alert and capture the webhook payload.** In SigNoz, create an error-rate alert on `cartservice` and a webhook notification channel pointing at `http://host.docker.internal:9099/webhook` (a throwaway `nc -l 9099` / tiny listener). Toggle the Scenario-1 flag to trip it. Copy the raw JSON POST body into `docs/day1-findings.md`.

Run: `nc -l 9099` (or `python -m http.server`-style catcher) while the alert fires.
Expected: the exact alert JSON (field names for status, labels, annotations, timestamps, threshold) recorded verbatim. This is the contract `detector` parses in Task 11.

- [ ] **Step 5: Confirm flagd flag names.** Read the pulled OTel Demo's `flagd` config (`flagd.json` / `demo.flagd.json`). Record the exact flag keys for the three chaos scenarios (spec §10 candidates: `cartServiceFailure`, `paymentServiceFailure`/`paymentServiceUnreachable`, `adServiceHighCpu`/`recommendationServiceCacheFailure`) into `docs/day1-findings.md`, plus the toggle mechanism (edit config file → hot reload, or flagd API).

Run: inspect the flagd config mounted by the demo compose.
Expected: exact flag names + the file path / API used to flip them.

- [ ] **Step 6: Confirm Anthropic credits (HUMAN GATE if credits must be purchased).** Verify `ANTHROPIC_API_KEY` works with a one-line `messages.create` smoke call using `claude-sonnet-5`. If no credits are available, **STOP and flag Mayank** (spending is a human gate).

Run: minimal `anthropic` SDK call.
Expected: a 200 response, recorded as "credits OK" in the artifact. On failure → flag, do not proceed to Task 12.

- [ ] **Step 7: Commit.**

```bash
git add casting.yaml casting.yaml.lock compose.yaml Makefile docs/day1-findings.md docs/decisions-log.md
git commit -m "chore: stand up SigNoz+MCP via Foundry, OTel Demo, capture day-1 findings"
```

---

### Task 2: Python project scaffold + config

**Files:**
- Create: `pyproject.toml`, `.env.example`, `sentinel/__init__.py`, `sentinel/config.py`, `tests/conftest.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Settings` (pydantic-settings) with fields `signoz_url: str`, `signoz_query_api_url: str`, `mcp_url: str`, `anthropic_api_key: str`, `anthropic_model: str = "claude-sonnet-5"`, `evidence_backend: str = "mcp"`, `flagd_config_path: str`, `audit_db_path: str = "sentinel.db"`, `otlp_endpoint: str`. Accessor `get_settings() -> Settings`.

- [ ] **Step 1: Write the failing test.**

```python
# tests/conftest.py — shared fixtures
import os, pytest
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SIGNOZ_URL", "http://signoz:8080")
    monkeypatch.setenv("SIGNOZ_QUERY_API_URL", "http://signoz:8080/api/v3")
    monkeypatch.setenv("MCP_URL", "http://mcp:8000")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("FLAGD_CONFIG_PATH", "/tmp/flagd.json")
    monkeypatch.setenv("OTLP_ENDPOINT", "http://signoz:4317")
```

```python
# tests/test_config.py
from sentinel.config import get_settings
def test_settings_load_from_env():
    s = get_settings()
    assert s.mcp_url == "http://mcp:8000"
    assert s.anthropic_model == "claude-sonnet-5"
    assert s.evidence_backend == "mcp"
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.config`.

- [ ] **Step 3: Write `pyproject.toml`** with deps (`fastapi`, `uvicorn`, `anthropic`, `mcp`, `httpx`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp`, `opentelemetry-instrumentation-fastapi`, `pyyaml`, `pydantic-settings`, `docker`) and dev deps (`pytest`, `pytest-asyncio`, `respx`, `playwright`), and configure pytest (`testpaths = ["tests"]`, `asyncio_mode = "auto"`).

- [ ] **Step 4: Write `sentinel/config.py`.**

```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    signoz_url: str
    signoz_query_api_url: str
    mcp_url: str
    anthropic_api_key: str
    anthropic_model: str = "claude-sonnet-5"
    evidence_backend: str = "mcp"          # "mcp" | "query_api"
    flagd_config_path: str
    audit_db_path: str = "sentinel.db"
    otlp_endpoint: str

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Run test to verify it passes.**

Run: `pip install -e ".[dev]" && pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add pyproject.toml .env.example sentinel/__init__.py sentinel/config.py tests/conftest.py tests/test_config.py
git commit -m "chore: python scaffold + env-driven settings"
```

---

### Task 3: Data models

**Files:**
- Create: `sentinel/models.py` (the "Locked data model" block above, verbatim)
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces: every type in the locked data model. All later tasks import from `sentinel.models`.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_models.py
from datetime import datetime
from sentinel.models import (
    Incident, Window, IncidentStatus, Action, ActionType,
    Hypothesis, Decision, DecisionMode, PolicyRule,
)
def test_incident_defaults_to_detected():
    inc = Incident(id="i1", source_alert={}, service="cartservice",
                   signal="error_rate", severity="critical",
                   window=Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)))
    assert inc.status is IncidentStatus.DETECTED

def test_hypothesis_carries_action():
    h = Hypothesis(root_cause="cart failing", rationale="5xx spike",
                   proposed_action=Action(ActionType.FLAG, "cartServiceFailure", {"value": False}),
                   confidence=0.9)
    assert h.proposed_action.type is ActionType.FLAG
    assert 0.0 <= h.confidence <= 1.0

def test_enums_are_str_serialisable():
    assert DecisionMode.AUTO == "auto"
    assert ActionType.FLAG.value == "flag"
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.models`.

- [ ] **Step 3: Write `sentinel/models.py`** — paste the "Locked data model" block above exactly.

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit.**

```bash
git add sentinel/models.py tests/test_models.py
git commit -m "feat: shared data models (incident, hypothesis, decision, action)"
```

---

## Phase 1 — Deterministic core (no external dependencies)

### Task 4: Policy engine

**Files:**
- Create: `sentinel/policy.py`, `policies/rules.yaml`
- Test: `tests/test_policy.py`

**Interfaces:**
- Consumes: `Hypothesis`, `Action`, `Decision`, `DecisionMode`, `PolicyRule` from `sentinel.models`.
- Produces: `load_policy(path: str) -> Policy`; `Policy.decide(hypothesis: Hypothesis, blast_radius: int) -> Decision`. Decision rules: pick the rule whose `action_type == hypothesis.proposed_action.type.value`; ESCALATE if no rule or target not in `allowed_targets`; APPROVE if `requires_approval` or `blast_radius > max_blast_radius` or `confidence < auto_execute_if_confidence_gte`; else AUTO.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_policy.py
from sentinel.policy import load_policy
from sentinel.models import Hypothesis, Action, ActionType, DecisionMode

RULES = "policies/rules.yaml"

def _hyp(atype, target, conf):
    return Hypothesis("rc", "why", Action(atype, target, {}), conf)

def test_low_risk_high_confidence_auto_heals():
    d = load_policy(RULES).decide(_hyp(ActionType.FLAG, "cartServiceFailure", 0.95), blast_radius=1)
    assert d.mode is DecisionMode.AUTO
    assert d.policy_rule_id

def test_high_blast_radius_needs_approval():
    d = load_policy(RULES).decide(_hyp(ActionType.SCALE, "adservice", 0.95), blast_radius=5)
    assert d.mode is DecisionMode.APPROVE

def test_low_confidence_needs_approval():
    d = load_policy(RULES).decide(_hyp(ActionType.FLAG, "cartServiceFailure", 0.4), blast_radius=1)
    assert d.mode is DecisionMode.APPROVE

def test_unknown_target_escalates():
    d = load_policy(RULES).decide(_hyp(ActionType.FLAG, "notARealTarget", 0.95), blast_radius=1)
    assert d.mode is DecisionMode.ESCALATE
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_policy.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.policy`.

- [ ] **Step 3: Write `policies/rules.yaml`.**

```yaml
rules:
  - id: flag-off
    action_type: flag
    risk: low
    auto_execute_if_confidence_gte: 0.75
    requires_approval: false
    max_blast_radius: 2
    allowed_targets: [cartServiceFailure, paymentServiceFailure, paymentServiceUnreachable]
  - id: restart-svc
    action_type: restart
    risk: med
    auto_execute_if_confidence_gte: 0.85
    requires_approval: false
    max_blast_radius: 1
    allowed_targets: [paymentservice, cartservice]
  - id: scale-svc
    action_type: scale
    risk: high
    auto_execute_if_confidence_gte: 0.99
    requires_approval: true
    max_blast_radius: 1
    allowed_targets: [adservice, recommendationservice]
```

- [ ] **Step 4: Write `sentinel/policy.py`.**

```python
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
```

- [ ] **Step 5: Run test to verify it passes.**

Run: `pytest tests/test_policy.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit.**

```bash
git add sentinel/policy.py policies/rules.yaml tests/test_policy.py
git commit -m "feat: policy engine (auto/approve/escalate from confidence x blast radius)"
```

---

### Task 5: Actuator protocol + FlagActuator

**Files:**
- Create: `sentinel/actuators/__init__.py`, `sentinel/actuators/flag.py`
- Test: `tests/test_actuators.py`

**Interfaces:**
- Consumes: `Action`, `ActionType`, `RemediationResult` from `sentinel.models`.
- Produces: `Actuator` protocol with attribute `type: ActionType` and method `apply(action: Action) -> RemediationResult`; `ActuatorRegistry` with `.register(actuator)` and `.get(action_type: ActionType) -> Actuator`; `FlagActuator(flagd_config_path: str)` that sets `flags[target].defaultVariant` to the safe variant (default `"off"`, overridable via `action.params["variant"]`) in the flagd JSON config and writes it back (flagd hot-reloads).

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_actuators.py
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
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_actuators.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.actuators`.

- [ ] **Step 3: Write `sentinel/actuators/__init__.py`.**

```python
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
```

- [ ] **Step 4: Write `sentinel/actuators/flag.py`.**

```python
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
```

- [ ] **Step 5: Run test to verify it passes.**

Run: `pytest tests/test_actuators.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit.**

```bash
git add sentinel/actuators/ tests/test_actuators.py
git commit -m "feat: actuator protocol + registry + FlagActuator"
```

---

### Task 6: Audit store

**Files:**
- Create: `sentinel/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: `Incident`, `Hypothesis`, `Decision`, `RemediationResult`, `VerificationResult`.
- Produces: `AuditStore(db_path: str)` with `.record(incident, hypothesis=None, decision=None, remediation=None, verification=None) -> None` (append-only, keyed by `incident.id`, upsert on repeated calls as the incident progresses) and `.get(incident_id: str) -> dict | None` returning the JSON record. Used by the orchestrator (Task 14) and the dashboard/metrics.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_audit.py
from datetime import datetime
from sentinel.audit import AuditStore
from sentinel.models import (Incident, Window, IncidentStatus, Hypothesis,
                             Action, ActionType, Decision, DecisionMode)

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)),
                    IncidentStatus.DETECTED)

def test_record_then_get(tmp_path):
    store = AuditStore(str(tmp_path / "a.db"))
    store.record(_inc())
    rec = store.get("i1")
    assert rec["service"] == "cartservice"
    assert rec["status"] == "DETECTED"

def test_record_upserts_decision(tmp_path):
    store = AuditStore(str(tmp_path / "a.db"))
    inc = _inc()
    store.record(inc)
    store.record(inc, decision=Decision(DecisionMode.AUTO,
        Action(ActionType.FLAG, "cartServiceFailure", {}), "flag-off", "ok"))
    assert store.get("i1")["decision"]["mode"] == "auto"
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_audit.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.audit`.

- [ ] **Step 3: Write `sentinel/audit.py`.**

```python
import json, sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from sentinel.models import Incident

def _enc(o):
    if is_dataclass(o):
        return {k: _enc(v) for k, v in asdict(o).items()}
    if isinstance(o, datetime):
        return o.isoformat()
    return o

class AuditStore:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, doc TEXT)")
        self.db.commit()

    def record(self, incident: Incident, hypothesis=None, decision=None,
               remediation=None, verification=None):
        cur = self.get(incident.id) or {}
        cur.update({"id": incident.id, "service": incident.service,
                    "signal": incident.signal, "status": incident.status.value})
        for key, val in [("hypothesis", hypothesis), ("decision", decision),
                         ("remediation", remediation), ("verification", verification)]:
            if val is not None:
                cur[key] = _enc(val)
        self.db.execute("INSERT INTO incidents(id, doc) VALUES(?,?) "
                        "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc",
                        (incident.id, json.dumps(cur)))
        self.db.commit()

    def get(self, incident_id: str):
        row = self.db.execute("SELECT doc FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return json.loads(row[0]) if row else None
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_audit.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit.**

```bash
git add sentinel/audit.py tests/test_audit.py
git commit -m "feat: append-only SQLite audit store"
```

---

## Phase 2 — SigNoz integration (reads `docs/day1-findings.md`)

### Task 8: SigNoz client — one interface, two backends

**Files:**
- Create: `sentinel/signoz_client.py`
- Test: `tests/test_signoz_client.py`

**Interfaces:**
- Consumes: `get_settings()`; the MCP tool names and Query API shapes recorded in `docs/day1-findings.md`.
- Produces: `SignozBackend` protocol with methods `get_metric(service, signal, start, end) -> float`, `get_traces(service, start, end, limit=20) -> list[dict]`, `get_logs(service, start, end, limit=50) -> list[dict]`, `get_topology() -> dict`; `QueryApiBackend(base_url)` (uses `/api/v3/query_range`, fully specifiable today); `McpBackend(mcp_url)` (maps each method to the MCP tool named in day-1 findings); `get_backend(settings) -> SignozBackend` selecting on `settings.evidence_backend`. **This is the spec §5.3 isolation seam — the only place that knows MCP vs REST.**

- [ ] **Step 1: Write the failing test** (backends are mocked; no live SigNoz needed).

```python
# tests/test_signoz_client.py
import respx, httpx
from datetime import datetime
from sentinel.signoz_client import QueryApiBackend, get_backend
from sentinel.config import get_settings

@respx.mock
def test_query_api_get_metric_parses_last_value():
    respx.post("http://signoz:8080/api/v3/query_range").mock(return_value=httpx.Response(
        200, json={"data": {"result": [{"series": [{"values": [[1, "0.0"], [2, "0.42"]]}]}]}}))
    v = QueryApiBackend("http://signoz:8080/api/v3").get_metric(
        "cartservice", "error_rate", datetime(2026,7,23,10), datetime(2026,7,23,10,5))
    assert v == 0.42

def test_get_backend_selects_query_api(monkeypatch):
    monkeypatch.setenv("EVIDENCE_BACKEND", "query_api")
    get_settings.cache_clear()
    assert type(get_backend(get_settings())).__name__ == "QueryApiBackend"
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_signoz_client.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.signoz_client`.

- [ ] **Step 3: Write `sentinel/signoz_client.py`.** Query API backend is complete now; MCP backend maps to the tool names captured in Task 1 (fill the `TOOL_*` constants from `docs/day1-findings.md`).

```python
from typing import Protocol
from datetime import datetime
import httpx
from mcp.client.session import ClientSession   # exact import per mcp SDK version

class SignozBackend(Protocol):
    def get_metric(self, service: str, signal: str, start: datetime, end: datetime) -> float: ...
    def get_traces(self, service: str, start: datetime, end: datetime, limit: int = 20) -> list: ...
    def get_logs(self, service: str, start: datetime, end: datetime, limit: int = 50) -> list: ...
    def get_topology(self) -> dict: ...

class QueryApiBackend:
    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def _query_range(self, payload: dict) -> dict:
        r = httpx.post(f"{self.base}/query_range", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_metric(self, service, signal, start, end) -> float:
        payload = _metric_query_payload(service, signal, start, end)   # built from findings
        data = self._query_range(payload)
        series = data["data"]["result"][0]["series"][0]["values"]
        return float(series[-1][1])

    def get_traces(self, service, start, end, limit=20) -> list:
        return self._query_range(_trace_query_payload(service, start, end, limit)) \
            .get("data", {}).get("result", [])

    def get_logs(self, service, start, end, limit=50) -> list:
        return self._query_range(_log_query_payload(service, start, end, limit)) \
            .get("data", {}).get("result", [])

    def get_topology(self) -> dict:
        r = httpx.get(f"{self.base}/service_map", timeout=30)   # endpoint per findings
        return r.json() if r.status_code == 200 else {}

class McpBackend:
    # Tool names filled from docs/day1-findings.md (Task 1, Step 3).
    TOOL_METRIC = "..."   # e.g. "signoz_query_metrics"
    TOOL_TRACES = "..."
    TOOL_LOGS = "..."
    TOOL_TOPOLOGY = "..."
    def __init__(self, mcp_url: str):
        self.url = mcp_url
    # each method opens an MCP session and call_tool(TOOL_*, {...}); shapes per findings.
    # If a tool is missing in the catalog, delegate that method to QueryApiBackend.

def get_backend(settings) -> SignozBackend:
    if settings.evidence_backend == "query_api":
        return QueryApiBackend(settings.signoz_query_api_url)
    return McpBackend(settings.mcp_url)
```

> Helper builders `_metric_query_payload` / `_trace_query_payload` / `_log_query_payload` are written against the exact Query API request shape recorded in `docs/day1-findings.md` Step 3–4. Keep them in this file.

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_signoz_client.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Live smoke against the running stack** (not a unit test — a manual gate).

Run: `python -c "from sentinel.config import get_settings; from sentinel.signoz_client import get_backend; from datetime import datetime,timedelta,timezone; e=datetime.now(timezone.utc); print(get_backend(get_settings()).get_metric('cartservice','error_rate', e-timedelta(minutes=5), e))"`
Expected: a float prints (0.0 when healthy). If MCP path errors, set `EVIDENCE_BACKEND=query_api` and record in decisions-log.

- [ ] **Step 6: Commit.**

```bash
git add sentinel/signoz_client.py tests/test_signoz_client.py
git commit -m "feat: SignozBackend interface + Query API + MCP backends (isolation seam)"
```

---

### Task 9: Evidence gathering

**Files:**
- Create: `sentinel/evidence.py`
- Test: `tests/test_evidence.py`

**Interfaces:**
- Consumes: `Incident`, `Evidence`, and a `SignozBackend`.
- Produces: `gather(incident: Incident, backend: SignozBackend) -> Evidence` — pulls the alerting metric, top error traces, recent error logs, and topology for `incident.service` over `incident.window`, and composes a short text `summary`. `blast_radius(evidence) -> int` = count of distinct downstream services touched in `evidence.topology` (default 1).

- [ ] **Step 1: Write the failing test** (backend is a fake).

```python
# tests/test_evidence.py
from datetime import datetime
from sentinel.evidence import gather, blast_radius
from sentinel.models import Incident, Window, IncidentStatus

class FakeBackend:
    def get_metric(self, *a): return 0.42
    def get_traces(self, *a, **k): return [{"name": "POST /checkout", "status": "ERROR"}]
    def get_logs(self, *a, **k): return [{"body": "cart error"}]
    def get_topology(self): return {"cartservice": ["checkoutservice", "frontend"]}

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)), IncidentStatus.DETECTED)

def test_gather_populates_all_channels():
    ev = gather(_inc(), FakeBackend())
    assert ev.metrics["error_rate"] == 0.42
    assert ev.traces and ev.logs
    assert "cartservice" in ev.summary

def test_blast_radius_counts_downstream():
    ev = gather(_inc(), FakeBackend())
    assert blast_radius(ev) == 2
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.evidence`.

- [ ] **Step 3: Write `sentinel/evidence.py`.**

```python
from sentinel.models import Incident, Evidence

def gather(incident: Incident, backend) -> Evidence:
    w = incident.window
    metric = backend.get_metric(incident.service, incident.signal, w.start, w.end)
    traces = backend.get_traces(incident.service, w.start, w.end)
    logs = backend.get_logs(incident.service, w.start, w.end)
    topology = backend.get_topology()
    summary = (f"{incident.service} {incident.signal}={metric} over "
               f"{w.start.isoformat()}..{w.end.isoformat()}; "
               f"{len(traces)} error traces, {len(logs)} error logs.")
    return Evidence(traces=traces, logs=logs, metrics={incident.signal: metric},
                    topology=topology, recent_deploys=[], summary=summary)

def blast_radius(evidence: Evidence) -> int:
    downstream = {svc for deps in evidence.topology.values() for svc in deps}
    return max(1, len(downstream))
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_evidence.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit.**

```bash
git add sentinel/evidence.py tests/test_evidence.py
git commit -m "feat: evidence gathering + blast-radius estimate"
```

---

### Task 10: Verifier

**Files:**
- Create: `sentinel/verifier.py`
- Test: `tests/test_verifier.py`

**Interfaces:**
- Consumes: `Incident`, `RemediationResult`, `VerificationResult`, a `SignozBackend`, and a `sleep` injectable.
- Produces: `verify(incident, remediation, backend, baseline: float, timeout_s: int = 90, poll_s: int = 10, sleep=time.sleep) -> VerificationResult` — re-queries `incident.signal` for `incident.service` on a poll loop until the metric returns to `<= baseline` (recovered) or `timeout_s` elapses. `metric_before` = value at first poll; `metric_after` = last value.

- [ ] **Step 1: Write the failing test** (fake backend returns a scripted sequence; sleep is a no-op).

```python
# tests/test_verifier.py
from datetime import datetime, timezone
from sentinel.verifier import verify
from sentinel.models import (Incident, Window, IncidentStatus, Action, ActionType, RemediationResult)

class SeqBackend:
    def __init__(self, seq): self.seq = list(seq)
    def get_metric(self, *a): return self.seq.pop(0)

def _rem():
    return RemediationResult(Action(ActionType.FLAG, "cartServiceFailure", {}),
                             datetime.now(timezone.utc), True, "ok")
def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)), IncidentStatus.VERIFYING)

def test_recovers_when_metric_drops_to_baseline():
    r = verify(_inc(), _rem(), SeqBackend([0.4, 0.2, 0.0]), baseline=0.05,
               timeout_s=60, poll_s=1, sleep=lambda s: None)
    assert r.recovered is True
    assert r.metric_after == 0.0

def test_times_out_when_metric_stays_high():
    r = verify(_inc(), _rem(), SeqBackend([0.4, 0.4, 0.4, 0.4, 0.4, 0.4, 0.4]),
               baseline=0.05, timeout_s=3, poll_s=1, sleep=lambda s: None)
    assert r.recovered is False
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_verifier.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.verifier`.

- [ ] **Step 3: Write `sentinel/verifier.py`.**

```python
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
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_verifier.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit.**

```bash
git add sentinel/verifier.py tests/test_verifier.py
git commit -m "feat: verifier poll loop (recovery vs timeout)"
```

---

### Task 11: Detector (webhook → Incident)

**Files:**
- Create: `sentinel/detector.py`
- Test: `tests/test_detector.py`

**Interfaces:**
- Consumes: the exact SigNoz alert webhook JSON recorded in `docs/day1-findings.md` Step 4; `Incident`, `Window`, `IncidentStatus`.
- Produces: `to_incident(payload: dict, now: datetime) -> Incident` — extracts service, signal, severity, and the alert time window from the SigNoz payload. Window = `[fire_time - lookback, fire_time]` with `lookback = 5 min`. `id` derived from the alert fingerprint/id in the payload.

> **Fill the field paths in Step 3 from the captured payload.** The test below uses a payload shaped like SigNoz's Alertmanager-compatible webhook (`{status, alerts:[{labels, annotations, startsAt}]}`); adjust the extraction to the real field names once Task 1 Step 4 is recorded.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_detector.py
from datetime import datetime, timezone
from sentinel.detector import to_incident
from sentinel.models import IncidentStatus

PAYLOAD = {
  "status": "firing",
  "alerts": [{
    "fingerprint": "abc123",
    "labels": {"alertname": "cart-error-rate", "service_name": "cartservice",
               "severity": "critical", "signal": "error_rate"},
    "annotations": {"description": "error rate > 5%"},
    "startsAt": "2026-07-23T10:05:00Z"}]
}

def test_to_incident_extracts_core_fields():
    inc = to_incident(PAYLOAD, now=datetime(2026,7,23,10,5,tzinfo=timezone.utc))
    assert inc.service == "cartservice"
    assert inc.signal == "error_rate"
    assert inc.severity == "critical"
    assert inc.status is IncidentStatus.DETECTED
    assert inc.id == "abc123"

def test_window_is_five_minute_lookback():
    inc = to_incident(PAYLOAD, now=datetime(2026,7,23,10,5,tzinfo=timezone.utc))
    assert (inc.window.end - inc.window.start).total_seconds() == 300
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_detector.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.detector`.

- [ ] **Step 3: Write `sentinel/detector.py`** (field paths per captured payload).

```python
from datetime import datetime, timedelta, timezone
from sentinel.models import Incident, Window, IncidentStatus

LOOKBACK = timedelta(minutes=5)

def to_incident(payload: dict, now: datetime) -> Incident:
    alert = payload["alerts"][0]
    labels = alert.get("labels", {})
    fire = alert.get("startsAt")
    end = datetime.fromisoformat(fire.replace("Z", "+00:00")) if fire else now
    return Incident(
        id=alert.get("fingerprint") or labels.get("alertname", "unknown"),
        source_alert=payload,
        service=labels.get("service_name", "unknown"),
        signal=labels.get("signal", "error_rate"),
        severity=labels.get("severity", "warning"),
        window=Window(end - LOOKBACK, end),
        status=IncidentStatus.DETECTED,
    )
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_detector.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit.**

```bash
git add sentinel/detector.py tests/test_detector.py
git commit -m "feat: detector normalises SigNoz alert webhook into Incident"
```

---

## Phase 3 — Reasoning

### Task 12: Reasoner (Claude)

**Files:**
- Create: `sentinel/reasoner.py`
- Test: `tests/test_reasoner.py`

**Interfaces:**
- Consumes: `Incident`, `Evidence`, `Hypothesis`, `Action`, `ActionType`, `get_settings()`, an `anthropic` client (injectable).
- Produces: `hypothesize(incident, evidence, client, model) -> Hypothesis` — sends a system prompt + the evidence summary and asks Claude to return a structured root cause, rationale, a proposed `Action` (type ∈ flag/restart/scale, target, params), and a `confidence` 0..1, via a forced tool call (`propose_remediation` tool schema). Parses the tool input into a `Hypothesis`.

- [ ] **Step 1: Write the failing test** (client is a fake returning a canned tool-use block).

```python
# tests/test_reasoner.py
from datetime import datetime
from sentinel.reasoner import hypothesize
from sentinel.models import Incident, Window, IncidentStatus, Evidence, ActionType

class FakeBlock:
    type = "tool_use"; name = "propose_remediation"
    input = {"root_cause": "cart flag failure", "rationale": "5xx from cartservice",
             "action_type": "flag", "target": "cartServiceFailure",
             "params": {"variant": "off"}, "confidence": 0.92}
class FakeMsg:
    content = [FakeBlock()]
class FakeClient:
    class messages:
        @staticmethod
        def create(**kw): return FakeMsg()

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10), datetime(2026,7,23,10,5)), IncidentStatus.INVESTIGATING)

def test_hypothesize_parses_tool_call():
    h = hypothesize(_inc(), Evidence(summary="cart 5xx spike"), FakeClient(), "claude-sonnet-5")
    assert h.proposed_action.type is ActionType.FLAG
    assert h.proposed_action.target == "cartServiceFailure"
    assert h.confidence == 0.92
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_reasoner.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.reasoner`.

- [ ] **Step 3: Write `sentinel/reasoner.py`.**

```python
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
    msg = client.messages.create(model=model, max_tokens=1024, system=SYSTEM,
                                 tools=[TOOL], tool_choice={"type": "tool", "name": "propose_remediation"},
                                 messages=[{"role": "user", "content": user}])
    block = next(b for b in msg.content if getattr(b, "type", None) == "tool_use")
    d = block.input
    action = Action(ActionType(d["action_type"]), d["target"], d.get("params", {}))
    return Hypothesis(d["root_cause"], d["rationale"], action, float(d["confidence"]))
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_reasoner.py -v`
Expected: PASS.

- [ ] **Step 5: Live smoke (uses real credits — small call).**

Run: a one-incident script against the real Anthropic client; confirm a sensible `flag`/`cartServiceFailure` hypothesis prints. Record token usage in decisions-log.
Expected: valid `Hypothesis`. On auth failure → this is the Task 1 Step 6 gate; flag Mayank.

- [ ] **Step 6: Commit.**

```bash
git add sentinel/reasoner.py tests/test_reasoner.py
git commit -m "feat: reasoner (Claude forced tool call -> Hypothesis)"
```

---

## Phase 4 — Orchestration, self-telemetry, serving

### Task 13: Telemetry (Sentinel traces itself)

**Files:**
- Create: `sentinel/telemetry.py`
- Test: `tests/test_telemetry.py`

**Interfaces:**
- Consumes: `get_settings()`.
- Produces: `setup_tracing(service_name: str = "sentinel", otlp_endpoint: str | None = None) -> None` (idempotent; installs an OTLP span exporter to SigNoz) and `tracer` (module-level `opentelemetry.trace.Tracer`) with a helper `span(name: str)` context manager. Every orchestrator stage opens a child span so one incident = one trace in SigNoz.

- [ ] **Step 1: Write the failing test** (in-memory exporter; no live SigNoz).

```python
# tests/test_telemetry.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sentinel import telemetry

def test_span_records_to_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    telemetry.tracer = trace.get_tracer("sentinel")
    with telemetry.span("detect"):
        pass
    names = [s.name for s in exporter.get_finished_spans()]
    assert "detect" in names
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_telemetry.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.telemetry`.

- [ ] **Step 3: Write `sentinel/telemetry.py`.**

```python
from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

_initialised = False
tracer = trace.get_tracer("sentinel")

def setup_tracing(service_name: str = "sentinel", otlp_endpoint: str | None = None) -> None:
    global _initialised, tracer
    if _initialised:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if otlp_endpoint:
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(service_name)
    _initialised = True

@contextmanager
def span(name: str):
    with tracer.start_as_current_span(name) as s:
        yield s
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_telemetry.py -v`
Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add sentinel/telemetry.py tests/test_telemetry.py
git commit -m "feat: OTel self-tracing setup + span helper"
```

---

### Task 14: Orchestrator (incident state machine)

**Files:**
- Create: `sentinel/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `evidence.gather`/`blast_radius`, `reasoner.hypothesize`, `policy.Policy.decide`, `ActuatorRegistry`, `verifier.verify`, `AuditStore`, `telemetry.span`, and all models.
- Produces: `Orchestrator(backend, anthropic_client, policy, registry, audit, model, baseline_fn=lambda inc: 0.05)` with:
  - `handle(incident) -> Incident` — runs DETECTED→INVESTIGATING→DIAGNOSED→(AUTO: REMEDIATING→VERIFYING→RESOLVED/FAILED | APPROVE: AWAITING_APPROVAL, stops | ESCALATE: ESCALATED), writing audit + a span per stage. Stores pending approvals in `self.pending[incident.id] = (incident, hypothesis, decision)`.
  - `approve(incident_id) -> Incident` — executes a previously-gated decision (REMEDIATING→VERIFYING→RESOLVED/FAILED).

- [ ] **Step 1: Write the failing test** (all collaborators faked; drives both the auto path and the approval path).

```python
# tests/test_orchestrator.py
from datetime import datetime, timezone
from sentinel.orchestrator import Orchestrator
from sentinel.policy import load_policy
from sentinel.actuators import ActuatorRegistry
from sentinel.actuators.flag import FlagActuator
from sentinel.audit import AuditStore
from sentinel.models import (Incident, Window, IncidentStatus, ActionType)

class Backend:  # healthy metric so verify() recovers immediately
    def get_metric(self,*a): return 0.0
    def get_traces(self,*a,**k): return []
    def get_logs(self,*a,**k): return []
    def get_topology(self): return {"cartservice": ["frontend"]}

def make_client(conf):
    class B: type="tool_use"; name="propose_remediation"; input={
        "root_cause":"cart","rationale":"5xx","action_type":"flag",
        "target":"cartServiceFailure","params":{"variant":"off"},"confidence":conf}
    class M: content=[B()]
    class C:
        class messages:
            @staticmethod
            def create(**kw): return M()
    return C()

def _inc():
    return Incident("i1", {}, "cartservice", "error_rate", "critical",
                    Window(datetime(2026,7,23,10,tzinfo=timezone.utc),
                           datetime(2026,7,23,10,5,tzinfo=timezone.utc)), IncidentStatus.DETECTED)

def _orch(client, cfg, flag_path):
    reg = ActuatorRegistry(); reg.register(FlagActuator(flag_path))
    return Orchestrator(Backend(), client, load_policy("policies/rules.yaml"), reg,
                        AuditStore(cfg), "claude-sonnet-5",
                        baseline_fn=lambda inc: 0.05)

def test_high_confidence_auto_heals_to_resolved(tmp_path):
    import json; fp = tmp_path/"flagd.json"
    fp.write_text(json.dumps({"flags":{"cartServiceFailure":{"defaultVariant":"on","variants":{"on":True,"off":False}}}}))
    o = _orch(make_client(0.95), str(tmp_path/"a.db"), str(fp))
    out = o.handle(_inc())
    assert out.status is IncidentStatus.RESOLVED

def test_low_confidence_awaits_then_approve_resolves(tmp_path):
    import json; fp = tmp_path/"flagd.json"
    fp.write_text(json.dumps({"flags":{"cartServiceFailure":{"defaultVariant":"on","variants":{"on":True,"off":False}}}}))
    o = _orch(make_client(0.4), str(tmp_path/"a.db"), str(fp))
    out = o.handle(_inc())
    assert out.status is IncidentStatus.AWAITING_APPROVAL
    resolved = o.approve("i1")
    assert resolved.status is IncidentStatus.RESOLVED
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.orchestrator`.

- [ ] **Step 3: Write `sentinel/orchestrator.py`.**

```python
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

    def approve(self, incident_id: str) -> Incident:
        incident, hyp, decision = self.pending.pop(incident_id)
        return self._execute(incident, hyp, decision)

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
```

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_orchestrator.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit.**

```bash
git add sentinel/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator incident state machine (auto + approval paths)"
```

---

### Task 15: FastAPI app (webhook + approval endpoints)

**Files:**
- Create: `sentinel/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `detector.to_incident`, `Orchestrator`, `get_settings`, `setup_tracing`, all wiring.
- Produces: FastAPI app with `POST /webhook` (SigNoz alert → `to_incident` → `orchestrator.handle` in a background task; returns 202 + incident id), `POST /incidents/{id}/approve` (→ `orchestrator.approve`), `GET /incidents/{id}` (→ audit record), `GET /healthz`. A module-level `build_app(orchestrator=None)` factory so tests inject a fake orchestrator.

- [ ] **Step 1: Write the failing test.**

```python
# tests/test_app.py
from fastapi.testclient import TestClient
from sentinel.app import build_app
from sentinel.models import Incident, Window, IncidentStatus
from datetime import datetime, timezone

class FakeOrch:
    def __init__(self): self.handled = None
    def handle(self, inc): self.handled = inc; inc.status = IncidentStatus.RESOLVED; return inc
    def approve(self, iid): return Incident(iid, {}, "cartservice","error_rate","critical",
        Window(datetime(2026,7,23,10,tzinfo=timezone.utc),datetime(2026,7,23,10,5,tzinfo=timezone.utc)),
        IncidentStatus.RESOLVED)

PAYLOAD = {"status":"firing","alerts":[{"fingerprint":"abc","labels":
    {"service_name":"cartservice","signal":"error_rate","severity":"critical"},
    "startsAt":"2026-07-23T10:05:00Z"}]}

def test_webhook_accepts_and_returns_incident_id():
    app = build_app(orchestrator=FakeOrch())
    r = TestClient(app).post("/webhook", json=PAYLOAD)
    assert r.status_code == 202
    assert r.json()["incident_id"] == "abc"

def test_healthz():
    assert TestClient(build_app(orchestrator=FakeOrch())).get("/healthz").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails.**

Run: `pytest tests/test_app.py -v`
Expected: FAIL — `ModuleNotFoundError: sentinel.app`.

- [ ] **Step 3: Write `sentinel/app.py`.**

```python
from fastapi import FastAPI, BackgroundTasks
from datetime import datetime, timezone
from sentinel.detector import to_incident

def build_app(orchestrator=None) -> FastAPI:
    app = FastAPI(title="Sentinel")
    app.state.orchestrator = orchestrator

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.post("/webhook", status_code=202)
    def webhook(payload: dict, bg: BackgroundTasks):
        incident = to_incident(payload, now=datetime.now(timezone.utc))
        bg.add_task(app.state.orchestrator.handle, incident)
        return {"incident_id": incident.id, "status": incident.status.value}

    @app.post("/incidents/{incident_id}/approve")
    def approve(incident_id: str):
        inc = app.state.orchestrator.approve(incident_id)
        return {"incident_id": inc.id, "status": inc.status.value}

    return app
```

> The production entrypoint (`app = build_app(_wire_real_orchestrator())`) that calls `setup_tracing`, builds the real `Orchestrator` from `get_settings()`, and is served by uvicorn lives at the bottom of this file, guarded so tests importing `build_app` don't construct real clients.

- [ ] **Step 4: Run test to verify it passes.**

Run: `pytest tests/test_app.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Full unit suite green.**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 6: Commit.**

```bash
git add sentinel/app.py tests/test_app.py
git commit -m "feat: FastAPI webhook + approval + health endpoints"
```

---

## Phase 5 — End-to-end: Scenario 1 auto-heal (the winning demo)

### Task 17: Chaos scenario + Makefile + E2E verification

**Files:**
- Create: `scenarios/flagd_chaos.py`
- Create: `tests/e2e/test_scenario1.py` (Playwright)
- Modify: `compose.yaml` (add the Sentinel service), `Makefile` (add `up`/`demo`/`verify`/`down`/`e2e`)

**Interfaces:**
- Consumes: the running full stack; `flagd` flag names from `docs/day1-findings.md`.
- Produces: `scenarios/flagd_chaos.py` with `inject(flag: str)` / `heal(flag: str)` (flip flagd flag on/off using the mechanism recorded in Task 1); `make verify` implementing CLAUDE.md §6.

- [ ] **Step 1: Add Sentinel to `compose.yaml`** — container running `uvicorn sentinel.app:app`, env from `.env`, `flagd` config mounted read-write, on the SigNoz + demo network. Register the SigNoz webhook channel + alert rules to point at `http://sentinel:8000/webhook`.

- [ ] **Step 2: Write `scenarios/flagd_chaos.py`.**

```python
import json, sys
def _set(flag: str, variant: str, path: str):
    cfg = json.load(open(path)); cfg["flags"][flag]["defaultVariant"] = variant
    json.dump(cfg, open(path, "w"), indent=2)
def inject(flag, path): _set(flag, "on", path)
def heal(flag, path):   _set(flag, "off", path)
if __name__ == "__main__":
    {"inject": inject, "heal": heal}[sys.argv[1]](sys.argv[2], sys.argv[3])
```

- [ ] **Step 3: Write the failing E2E test** `tests/e2e/test_scenario1.py`.

```python
# Playwright + HTTP: inject fault -> assert Sentinel resolves the incident.
import time, json, httpx
from scenarios.flagd_chaos import inject
FLAG = "cartServiceFailure"   # from docs/day1-findings.md
SENTINEL = "http://localhost:8000"
FLAGD = "/path/to/flagd.json" # from findings

def test_scenario1_auto_heals():
    inject(FLAG, FLAGD)                         # trip the fault
    incident_id = None
    for _ in range(30):                         # alert fires -> webhook -> orchestrator
        r = httpx.get(f"{SENTINEL}/incidents/latest")
        if r.status_code == 200 and r.json().get("id"):
            incident_id = r.json()["id"]; break
        time.sleep(5)
    assert incident_id, "Sentinel never received an alert"
    for _ in range(30):
        rec = httpx.get(f"{SENTINEL}/incidents/{incident_id}").json()
        if rec["status"] in ("RESOLVED", "FAILED"): break
        time.sleep(5)
    assert rec["status"] == "RESOLVED"
    assert rec["verification"]["recovered"] is True
```

> Add a `GET /incidents/latest` route to `sentinel/app.py` returning the most recent audit record (small addition; commit with this task).

- [ ] **Step 4: Write `Makefile`.**

```makefile
up:      ; foundryctl cast && docker compose up -d
down:    ; docker compose down
demo:    ; python -m scenarios.flagd_chaos inject cartServiceFailure $(FLAGD)
verify:  ; docker compose ps && pytest -q && pytest -q tests/e2e/test_scenario1.py
e2e:     ; pytest -q tests/e2e/test_scenario1.py
```

- [ ] **Step 5: Run the full stack and E2E.**

Run: `make up && sleep 90 && make verify`
Expected: containers healthy; unit suite green; Scenario 1 ends `RESOLVED` with `recovered=True`. Confirm in the SigNoz UI that one Sentinel trace exists with spans `incident → investigate → hypothesize → decide → remediate → verify`.

- [ ] **Step 6: Commit.**

```bash
git add scenarios/ tests/e2e/ Makefile compose.yaml sentinel/app.py
git commit -m "feat: scenario-1 auto-heal end-to-end + make verify gate"
```

---

## Phase 6 — Self-observability dashboard (not cuttable)

### Task 16: Sentinel Ops dashboard

**Files:**
- Create: `dashboards/sentinel-ops.json`
- Modify: `Makefile` (add `dashboard-import`)

**Interfaces:**
- Consumes: Sentinel's own traces/spans (Task 13) + audit metrics.
- Produces: a SigNoz dashboard JSON with panels: **MTTR** (avg incident→resolved span duration), **fix-success rate** (RESOLVED / total), **human-approval rate** (AWAITING_APPROVAL / total), **tokens per incident** (from reasoner span attribute), **incidents over time**. Importable via SigNoz dashboard API.

- [ ] **Step 1: Emit the metrics the panels need.** In `reasoner.py`, set span attributes `sentinel.tokens_in`/`sentinel.tokens_out` from the Anthropic response `usage`; in `orchestrator.py`, set `sentinel.decision_mode` and `sentinel.resolved` on the `incident` span. (Small edits; TDD via a span-attribute assertion added to `test_orchestrator.py`.)

- [ ] **Step 2: Build the dashboard** in the SigNoz UI against live Sentinel traces, then export JSON to `dashboards/sentinel-ops.json`.

- [ ] **Step 3: Add `make dashboard-import`** posting the JSON to the SigNoz dashboards API so judges get it on re-deploy.

- [ ] **Step 4: Verify** the dashboard renders with live data after a demo run.

Run: `make demo && make dashboard-import` then open the dashboard.
Expected: all five panels render with non-empty data.

- [ ] **Step 5: Commit.**

```bash
git add dashboards/sentinel-ops.json Makefile sentinel/reasoner.py sentinel/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: Sentinel Ops dashboard + self-metrics (MTTR, success, approval rate, tokens)"
```

---

## Phase 7 — Submission (human gates)

### Task 18: README, demo video, disclosure, submission

**Files:**
- Create/finalize: `README.md`
- Create: `docs/blog-draft.md`

- [ ] **Step 1: Write `README.md`** — one-line pitch, architecture diagram (from spec §4), **one-command setup** (`make up`), the demo script (`make demo`), the judging-criteria mapping, and an explicit **"Built with Claude — AI assistance disclosed"** section (DQ-protection constraint).

- [ ] **Step 2: Record the demo video** — break (`make demo`) → SigNoz alert fires → Sentinel diagnoses → auto-heals → verifies → show the Sentinel trace + Ops dashboard. Keep < 3 min.

- [ ] **Step 3: Draft the tutorial blog** in `docs/blog-draft.md` (~1000–1500 words, real code + screenshots) for Medium/Dev.to/Substack.

- [ ] **Step 4: HUMAN GATES — STOP and get Mayank for each:**
  - Make the repo public / push to remote.
  - Publish the blog.
  - Submit the registration + project forms (spec §15 links).
  - Confirm the AI-disclosure text before anything goes public.

- [ ] **Step 5: Commit (local).**

```bash
git add README.md docs/blog-draft.md
git commit -m "docs: README (setup+demo+AI disclosure) + blog draft"
```

---

## Stretch (only after `make verify` is green end-to-end; cut first under time pressure)

### Task 19: Governance path — Scenario 3 + RestartActuator + ScaleActuator

**Files:** Create `sentinel/actuators/restart.py` (Docker SDK container restart), `sentinel/actuators/scale.py`; add tests mirroring Task 5; register both in the production wiring; add Scenario 2/3 flags to `scenarios/flagd_chaos.py`.

- [ ] Write `RestartActuator`/`ScaleActuator` (TDD, same shape as `FlagActuator`) → register → drive Scenario 3 (`adServiceHighCpu`) through the **human-approval** path (`POST /incidents/{id}/approve`) end-to-end → assert both governance modes demoable. Commit per actuator.

### Task 20: Thin incident-feed UI (Next.js) or Slack feed

**Files:** Create `ui/` (Next.js) polling `GET /incidents/*`, rendering the lifecycle `detected → diagnosing → proposed → (awaiting approval) → applied → verified` with approve/reject buttons; OR a Slack incident feed via Composio (CLAUDE.md §5 — Composio only for stretch human-in-the-loop).

- [ ] Build the feed, wire approve/reject to the approval endpoint, capture in the demo video. Commit.

---

## Self-review (run against the spec)

**1. Spec coverage** — every spec success criterion (§2) maps to a task:
- Real system + telemetry → Task 1. Alert reaches Sentinel automatically → Tasks 1, 11, 15, 17. Evidence via MCP + correct root cause → Tasks 8, 9, 12. Policy auto vs approval → Tasks 4, 14, 19. Apply + verify recovery → Tasks 5, 10, 14, 17. Sentinel self-trace + dashboard + audit → Tasks 6, 13, 16. Foundry re-deploy via `casting.yaml(.lock)` → Task 1. Spec modules §5.3 all have a task (detector 11, evidence 9, reasoner 12, policy 4, actuators 5/19, verifier 10, orchestrator 14, telemetry 13, audit 6). Chaos scenarios §10 → Task 17 (Scenario 1), Task 19 (Scenarios 2–3). Submission checklist §15 → Task 18.

**2. Placeholder scan** — the only deliberately-deferred literals are (a) `McpBackend.TOOL_*` names and the Query API payload builders in Task 8, and (b) `detector` field paths + the flagd flag names/paths in Tasks 11/17. All four are **explicitly sourced from `docs/day1-findings.md` (Task 1)** — they are unknowable until the environment is up, which is why Task 1 is first and gated. No other TODO/TBD/"handle edge cases" placeholders exist; every code step ships real code.

**3. Type consistency** — signatures verified across tasks: `get_metric(service, signal, start, end)` used identically in `QueryApiBackend`, `evidence.gather`, and `verifier.verify`; `Actuator.apply(action) -> RemediationResult` matches registry dispatch and orchestrator `_execute`; `Policy.decide(hypothesis, blast_radius)` matches orchestrator call with `ev.blast_radius(evidence)`; `hypothesize(incident, evidence, client, model)` matches orchestrator + reasoner test; `Orchestrator.handle/approve` return `Incident` and match `app.py` usage; `AuditStore.record(...)` keyword args match every call site.

**Note on the compressed timeline:** Tasks 1–18 are the non-cuttable winning MVP. If Jul 25 arrives with Tasks 1–17 not fully green, the cut order is Task 20 → Task 19 → Task 16 polish, and Scenario 1 auto-heal + self-trace + README + disclosed video is the minimum viable submission.
