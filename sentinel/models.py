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
