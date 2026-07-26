# Sentinel — Design Spec

> An autonomous, policy-gated SRE copilot that watches a live system through SigNoz,
> diagnoses incidents via the SigNoz MCP server + Claude, applies a guarded fix, and
> **verifies recovery** — a closed self-healing loop, not just a diagnosis chatbot.

| | |
|---|---|
| **Project** | Sentinel |
| **Event** | Agents of SigNoz Hackathon (WeMakeDevs × SigNoz, sponsored by AWS) |
| **Track** | Track 01 — AI & Agent Observability |
| **Team** | Solo build + Claude (autonomous builder) |
| **Hackathon window** | Jul 20–26, 2026 |
| **Spec date** | 2026-07-15 |
| **Status** | Approved design — implemented (see `implementation-plan.md` and the repo) |

---

## 1. Context & goal

The hackathon's thesis: *"If you can't observe your AI agents, you don't own them"* — and, from
SigNoz's own agent-native framing, *"agents gather evidence and propose causes; humans set policy
and decide what deserves escalation."*

**Goal:** build the most convincing embodiment of that thesis. Sentinel is an AI on-call engineer
that turns SigNoz telemetry into autonomous-but-governed incident response. The differentiator vs.
SigNoz's own "Noz" assistant is the **policy/guardrail layer + closed verification loop + Sentinel
observing itself** — it doesn't just answer questions, it *acts within guardrails and proves the fix
worked*.

**Why it matters:** it sits dead-center on Track 01, exercises the fullest possible surface of SigNoz
(traces + logs + metrics + dashboards + alerts + MCP + Sentinel's own telemetry), and produces a
"break it live, watch it self-heal in under a minute" demonstration of governed autonomy.

## 2. Success criteria

**Target demo (must be true):**
1. A real distributed system (OTel Demo) runs and streams telemetry into SigNoz.
2. Injecting a fault causes a SigNoz alert to fire and reach Sentinel automatically.
3. Sentinel gathers correlated evidence via the SigNoz MCP server and states a correct root cause.
4. Sentinel's policy engine chooses auto-heal vs. human-approval based on confidence × blast radius.
5. Sentinel applies the remediation and then **verifies** the signal returns to baseline.
6. Sentinel's own decision process is visible as a trace + dashboard inside SigNoz, with an audit trail.
7. The repo re-deploys via Foundry from `casting.yaml` + `casting.yaml.lock`.

**Judging-criteria mapping:**

| Criterion | How Sentinel scores |
|---|---|
| Potential Impact | Autonomous incident response is real, expensive on-call pain |
| Creativity & Innovation | Policy guardrail + closed verify loop + observing-the-observer |
| Technical Excellence | MCP client + agent reasoning + policy engine + actuators + verification |
| **Best Use of SigNoz** | traces+logs+metrics+dashboards+alerts+MCP **and** Sentinel's own telemetry |
| User Experience | Live incident timeline (UI or Slack feed), clean dashboards |
| Presentation Quality | Live self-heal demo + README + tutorial blog |

## 3. Non-goals (YAGNI)

- Not a general-purpose observability product or a Noz replacement.
- No multi-tenant, auth, or production hardening — this is a hackathon demo.
- No custom ML models; reasoning is Claude via the Anthropic API.
- No Kubernetes for the MVP — Docker Compose only (K8s is an explicit non-goal for the week).
- No broad remediation catalog — a small, well-chosen set of safe actuators.

## 4. System overview

```
                    ┌────────── chaos: flip flagd flag ──────────┐
                    ▼                                             │
   ┌─────────────────────────────┐   OTLP    ┌──────────────────────────────┐
   │  OpenTelemetry Demo (~15 svc)│ ────────► │  SigNoz (deployed via Foundry)│
   │  astronomy shop + flagd      │           │  traces·logs·metrics·dashboards│
   └─────────────────────────────┘           │  alerts  +  MCP server :8000   │
                    ▲                          └───────┬───────────────┬──────┘
        remediation │                        alert webhook       MCP queries
   (disable flag / restart / scale)                  │                │
                    │                                 ▼                ▼
              ┌───────────────────────────────────────────────────────────┐
              │                    SENTINEL (Python)                        │
              │  detector → evidence → reasoner → policy → actuators →       │
              │  verifier   (orchestrated as an incident state machine)     │
              │  → emits its OWN OTel traces to SigNoz + writes audit trail  │
              └───────────────────────────────────────────────────────────┘
                                     │
                          thin UI / Slack incident feed (stretch)
```

## 5. Components

### 5.1 System under observation — OpenTelemetry Demo
- The official OTel Demo (astronomy webstore, ~15 polyglot microservices + load generator), unmodified.
- Exports OTLP → SigNoz.
- Faults are injected by toggling **`flagd`** feature flags (no code changes to the demo). This is the
  key elegance: the chaos source is a flag, and the natural remediation is "turn the bad flag off."

### 5.2 SigNoz + Foundry
- Self-hosted SigNoz deployed via **Foundry** (`foundryctl cast`), Docker/compose flavor.
- `casting.yaml` + `casting.yaml.lock` committed to the repo (required hackathon deliverable; judges
  re-run it).
- **MCP server enabled** on port 8000 (off by default in Foundry — we explicitly turn it on).
- Alert rules on error rate and p99 latency, routed to Sentinel via a **webhook notification channel**.

### 5.3 Sentinel (the core build — Python)
Decomposed into small, independently testable units, each with one purpose and a clear interface:

| Module | Purpose | Input → Output |
|---|---|---|
| `detector` | Receive SigNoz alert webhook, normalize | `AlertPayload → Incident` |
| `evidence` | Gather correlated evidence from SigNoz (MCP primary, Query API fallback) | `Incident → Evidence` |
| `reasoner` | Claude forms root-cause hypothesis + proposed action + confidence | `(Incident, Evidence) → Hypothesis` |
| `policy` | Decide auto / approve / escalate from confidence × blast radius | `Hypothesis → Decision` |
| `actuators` | Pluggable executors implementing a common interface | `Action → RemediationResult` |
| `verifier` | Re-query SigNoz until baseline restored or timeout | `(Incident, RemediationResult) → VerificationResult` |
| `orchestrator` | Drive the incident state machine, emit self-telemetry, write audit | wires the pipeline |
| `telemetry` | OTel setup so Sentinel traces itself into SigNoz | cross-cutting |
| `audit` | Persist a structured record of every incident + decision | append store (SQLite/JSON) |

**Key isolation decision:** `evidence` hides *how* evidence is fetched (MCP vs. REST Query API) behind
one interface. This de-risks the MCP-is-beta uncertainty — if MCP tools are thin, the fallback is a
config flag, not a rewrite.

### 5.4 Policy engine (the differentiator)
- Rules keyed by `action_type`, each with: `risk` (low/med/high), `auto_execute_if_confidence_gte`,
  `requires_approval`, `allowed_targets`, and a global **blast-radius guard** (e.g., never auto-act on
  more than N services at once).
- Two demoable paths: an **error incident** that auto-heals, and a **latency incident** whose fix is
  higher blast-radius → routed to **human approval** (Slack/CLI), showing both governance modes.

### 5.5 Actuators (small, safe set)
- `FlagActuator` — flip a `flagd` flag off (rewrite flagd config file / API; flagd hot-reloads). Low risk.
- `RestartActuator` — restart a container via the Docker SDK. Medium risk.
- `ScaleActuator` — scale replicas / adjust resources. Medium risk.
- (Stretch) `RollbackActuator` — redeploy previous image tag.

### 5.6 Self-observability + audit
- Sentinel emits one OTel trace per incident with spans: `detect → investigate (MCP calls) →
  hypothesize (LLM) → decide (policy) → remediate → verify`.
- A **"Sentinel Ops" SigNoz dashboard**: MTTR, fix-success rate, tokens per incident, human-approval
  rate, incidents over time. This is the deepest "Best Use of SigNoz" evidence.
- Audit store: append-only record per incident (hypothesis, evidence refs, decision, action, outcome).

### 5.7 Thin UI (stretch, only after MVP)
- Next.js incident cards: `detected → diagnosing → proposed → (awaiting approval) → applied → verified`,
  with approve/reject buttons for gated actions. If time is short, a Slack incident feed substitutes.

## 6. Incident lifecycle (state machine)

```
DETECTED → INVESTIGATING → DIAGNOSED
   → (safe)   REMEDIATING → VERIFYING → RESOLVED
   → (risky)  AWAITING_APPROVAL → REMEDIATING → VERIFYING → RESOLVED
   → (fail)   ESCALATED | FAILED
```

Flow: `flag flipped → bad telemetry → SigNoz alert → webhook → detector builds Incident →
evidence gathers via MCP → reasoner (Claude) → policy gate → actuator fixes → verifier confirms
recovery → audit + self-trace written → UI/Slack updated`.

## 7. Key data models (interfaces)

```
Incident      { id, source_alert, service, signal, severity, window, status }
Evidence      { traces[], logs[], metrics[], topology, recent_deploys, summary }
Hypothesis    { root_cause, rationale, proposed_action: Action, confidence: 0..1 }
Action        { type: flag|restart|scale|rollback, target, params }
Decision      { mode: auto|approve|escalate, action, policy_rule_id, reason }
Remediation-  { action, applied_at, ok, detail }
  Result
Verification- { recovered: bool, metric_before, metric_after, checked_until }
  Result
PolicyRule    { action_type, risk, auto_execute_if_confidence_gte,
                requires_approval, allowed_targets }
```

## 8. Tech stack & repo layout

- **Sentinel:** Python (strongest MCP-client + Anthropic SDK + OpenTelemetry ecosystem).
- **Reasoning:** Claude via the Anthropic API (tool use / MCP).
- **Everything in Docker Compose** for one-command reproducibility (aligns with Foundry + judges re-run).
- **UI (if built):** Next.js/React.

```
sentinel/
├── casting.yaml            # Foundry — SigNoz + MCP (committed)
├── casting.yaml.lock       # Foundry lockfile (committed)
├── compose.yaml            # OTel Demo + Sentinel (+ UI)
├── Makefile                # one-command setup: foundry cast + demo up + sentinel up
├── sentinel/               # the Python agent (modules from §5.3)
├── policies/               # policy rules (YAML)
├── dashboards/             # SigNoz dashboard JSON (Sentinel Ops)
├── scenarios/              # scripted chaos scenarios (§10)
├── ui/                     # Next.js incident feed (stretch)
├── docs/                   # this spec + decisions log + blog draft
└── README.md               # setup, architecture, demo script
```

## 9. Deployment & reproducibility
- `make up` → `foundryctl cast` (SigNoz + MCP) → OTel Demo up → Sentinel up → alert channel + rules loaded.
- Repo ships `casting.yaml` + `casting.yaml.lock` so judges reproduce the SigNoz deployment exactly.
- A `make demo` target runs a scripted incident end-to-end for the video / live run.

## 10. Chaos scenarios (variety across the policy paths)

| # | Fault (flagd flag) | Symptom in SigNoz | Expected root cause | Remediation | Policy path |
|---|---|---|---|---|---|
| 1 | `cartFailure` | checkout 5xx, cart error-rate spike | cart service returning errors | disable flag (`FlagActuator`) | low risk → **auto-heal** |
| 2 | `paymentFailure` / `paymentUnreachable` | checkout fails at payment step | payment failing/unreachable | disable flag; if unreachable, restart | low/med → **auto with guard** |
| 3 | `adHighCpu` / `recommendationCacheFailure` | p99 latency spike, CPU saturation | CPU/cache storm | scale/restart | higher blast radius → **human approval** |

> Flag keys verified against the pulled OTel Demo (`src/flagd/demo.flagd.json`); see `day1-findings.md`.

## 11. Scope — MVP vs stretch

**MVP (the winning core, demoable by mid-week):**
- Foundry → SigNoz + MCP + OTel Demo wired; telemetry flowing.
- Scenarios 1–3 scripted via `flagd`.
- Full Sentinel loop end-to-end (detect → … → verify) on those scenarios.
- Sentinel self-telemetry + Sentinel Ops dashboard + structured audit trail.
- README + demo video.

**Stretch (only if MVP is solid):** polished web UI w/ approval buttons · Slack human-approval ·
compound multi-fault incidents · `RollbackActuator` · cost/confidence-calibration dashboard.

## 12. Timeline (Jul 20–26) — de-risk integrations Day 1

| Day | Focus |
|---|---|
| D1 (20) | Foundry→SigNoz+MCP up · OTel Demo up · **prove MCP query + alert webhook end-to-end** (the two scary integrations, first) |
| D2 (21) | `flagd` chaos scenarios · SigNoz alert rules · Sentinel skeleton producing a root-cause hypothesis |
| D3 (22) | Policy engine + actuators · one scenario heals end-to-end |
| D4 (23) | Verify loop · self-telemetry · Sentinel Ops dashboard · scenarios 2–3 |
| D5 (24) | UI/Slack feed (stretch) · audit polish |
| D6 (25) | README · tutorial blog · demo video · dry runs |
| D7 (26) | Buffer + submit (repo has `casting.yaml` + `casting.yaml.lock`) |

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| SigNoz MCP tool surface is beta/limited | `evidence` interface hides MCP vs. **Query API** fallback; verify D1 |
| OTel Demo RAM (~6GB) | run a trimmed subset of services if constrained |
| Alert webhook wiring uncertainty | SigNoz supports webhook channels; prove D1 before building on it |
| Actuator safety (Docker socket, flag writes) | scope to demo only; guard by policy + allowed_targets |
| Solo time crunch | MVP scoped to mid-week; stretch strictly after; front-load risk |

## 14. Open questions / decisions to confirm on Day 1
- Exact `flagd` flag names + toggling mechanism for the pulled OTel Demo version.
- SigNoz MCP tool catalog (what queries are exposed) → confirms how much falls to the Query API.
- Alert webhook payload schema (to write `detector`).
- Whether Anthropic API access/credits are in hand for the week.

## 15. Submission checklist
- [ ] Registered for the hackathon
- [ ] Project submitted
- [ ] Repo public with `casting.yaml` + `casting.yaml.lock`
- [ ] AI-assistance disclosed (required)
- [ ] README with architecture + one-command setup + demo script
- [ ] Demo video (break → self-heal → verify)
- [ ] Tutorial blog on Medium/Dev.to/Substack (~1000–1500 words, real code + screenshots)

## 16. References
- Hackathon: https://www.wemakedevs.org/hackathons/signoz · rules: /hackathons/signoz/rules · blog guide: /hackathons/signoz/blog-guide
- SigNoz agent-native / MCP: https://signoz.io/agent-native-observability/
- Foundry: https://github.com/SigNoz/foundry · blog: https://signoz.io/blog/introducing-signoz-foundry/
- OTel Demo: https://opentelemetry.io/docs/demo/
- SigNoz repo: https://github.com/SigNoz/signoz · project board: https://github.com/orgs/SigNoz/projects/65
