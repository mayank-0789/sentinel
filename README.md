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
| `compose.yaml` · `Dockerfile` · `Makefile` | run Sentinel + one-command stack orchestration |
| `deploy/otelcol-config-extras.yml` | routes the OTel Demo's telemetry into SigNoz |
| `scenarios/inject.py` | flip a flagd flag to inject / clear a fault |
| `docs/` | design spec, implementation plan, Day-1 findings |

## Run the tests

```bash
python -m venv .venv && . .venv/bin/activate   # Python 3.11+
pip install -e '.[dev]'
pytest -q                                        # 42 passing
```

## Run it live

**Prerequisites:** Docker, [`foundryctl`](https://github.com/SigNoz/foundry), Python 3.11+.

```bash
cp .env.example .env         # set SIGNOZ_API_KEY (below); ANTHROPIC_API_KEY optional
make up                      # SigNoz (Foundry) + OTel Demo (wired to SigNoz) + Sentinel
```

One-time SigNoz setup (first run):
1. Open http://localhost:8080 and create the admin user.
2. **Settings → API Keys** → create a key → set it in `.env` as `SIGNOZ_API_KEY`.
3. **Settings → Alert Channels** → add a **Webhook** → `http://host.docker.internal:9099/webhook`.
4. Add an alert rule (e.g. cart-service error rate) routed to that channel.

Then drive the incident:

```bash
make demo      # flip the `cartFailure` flag on → SigNoz alerts → Sentinel diagnoses,
               # applies the guarded fix, and verifies recovery
make verify    # unit tests + live health check
make down      # tear it all down
```

**Reasoner modes:** with no `ANTHROPIC_API_KEY`, the reasoner runs as an offline **stub** (canned
hypothesis, no spend) so the whole loop still runs end-to-end; set a real key to enable live Claude
root-cause diagnosis. Every other stage — evidence, policy, remediation, verification, self-telemetry,
audit — behaves identically either way.

> **Verified:** the unit suite (42 tests) is green, the live SigNoz stack is healthy, and flag-toggle
> remediation is confirmed against the real demo config. The alert→webhook→heal→verify path uses the
> SigNoz setup above plus your own (or the stub) reasoner.

## Design

Full architecture, the 9 modules, data models, scope, and timeline live in the design spec:
[`docs/design.md`](docs/design.md).

---

*Built autonomously with [Claude](https://www.anthropic.com/claude) via Claude Code — design,
implementation, tests, and this README. AI assistance is disclosed per the hackathon rules.*
