# 🛰️ Sentinel

An autonomous, **policy-gated SRE copilot**. Sentinel watches a live system through
[SigNoz](https://signoz.io), and when an incident fires it uses the **SigNoz MCP server + Claude**
to find root cause, applies a guarded remediation, and **verifies recovery** — a closed self-healing
loop, not just a diagnosis chatbot.

Built for the **Agents of SigNoz** hackathon (WeMakeDevs × SigNoz) — Track 01: AI & Agent Observability.

> *"Agents gather evidence and propose causes; humans set policy and decide what deserves escalation."*
> Sentinel is that thesis, made real.

## Status

**Core implementation complete; live-stack integration in progress.**

- ✅ The full decision loop is implemented as 13 small Python modules and covered by **42 passing unit
  tests** — every stage is exercised with faked collaborators (SigNoz, Claude, the actuator).
- ✅ SigNoz is cast via Foundry (`casting.yaml` + `casting.yaml.lock` are committed; judges can re-run).
- 🚧 **Not yet proven end-to-end against a live stack.** Wiring the OTel Demo + SigNoz + Claude
  together (`compose.yaml`, `Makefile`, capturing the real MCP tool names / alert-webhook payload /
  `flagd` flag keys, and a Playwright scenario run) is the current step. Until that lands, the loop is
  verified at the unit level, not against live telemetry — this README will say so plainly until it is.

## How it works

1. The OpenTelemetry Demo runs and streams telemetry into SigNoz (deployed via Foundry).
2. A fault is injected (a `flagd` feature flag) → SigNoz alert fires → webhook to Sentinel.
3. Sentinel gathers correlated evidence via the SigNoz MCP server; Claude forms a root-cause hypothesis.
4. A policy engine chooses auto-heal vs. human-approval (confidence × blast radius).
5. Sentinel applies the fix, then re-queries SigNoz to confirm the signal returned to baseline.
6. Sentinel traces its own decision process into SigNoz and writes an audit trail.

## Repo map

| Path | What |
|---|---|
| `sentinel/detector.py` | SigNoz alert webhook → `Incident` |
| `sentinel/evidence.py` | Correlated evidence gathering + blast-radius estimate |
| `sentinel/reasoner.py` | Claude (forced tool call) → root-cause `Hypothesis` |
| `sentinel/policy.py` | confidence × blast radius → auto / approve / escalate |
| `sentinel/actuators/` | actuator protocol + `flagd` remediation |
| `sentinel/verifier.py` | poll SigNoz for recovery vs. timeout |
| `sentinel/orchestrator.py` | incident state machine (auto + approval paths) |
| `sentinel/signoz_client.py` | one interface, two backends (Query API + MCP) |
| `sentinel/audit.py` | append-only SQLite audit trail |
| `sentinel/telemetry.py` | Sentinel traces its own decisions into SigNoz |
| `sentinel/app.py` | FastAPI (webhook + approval + health) |
| `policies/rules.yaml` | policy rules |
| `casting.yaml` / `.lock` | Foundry cast of SigNoz + MCP server |

## Run the tests

```bash
python -m venv .venv && . .venv/bin/activate   # Python 3.11+
pip install -e '.[dev]'
pytest -q                                        # 42 passing
```

## Design

Full architecture, the 9 modules, data models, scope, and timeline live in the design spec:
[`docs/superpowers/specs/2026-07-15-sentinel-sre-copilot-design.md`](docs/superpowers/specs/2026-07-15-sentinel-sre-copilot-design.md).

---

*Built autonomously with [Claude](https://www.anthropic.com/claude) via Claude Code — design,
implementation, tests, and this README. AI assistance is disclosed per the hackathon rules.*
