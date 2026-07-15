# 🛰️ Sentinel

An autonomous, **policy-gated SRE copilot**. Sentinel watches a live system through
[SigNoz](https://signoz.io), and when an incident fires it uses the **SigNoz MCP server + Claude**
to find root cause, applies a guarded remediation, and **verifies recovery** — a closed self-healing
loop, not just a diagnosis chatbot.

Built for the **Agents of SigNoz** hackathon (WeMakeDevs × SigNoz) — Track 01: AI & Agent Observability.

> *"Agents gather evidence and propose causes; humans set policy and decide what deserves escalation."*
> Sentinel is that thesis, made real.

## Status
🚧 Pre-build. Design is approved and lives in
[`docs/superpowers/specs/2026-07-15-sentinel-sre-copilot-design.md`](docs/superpowers/specs/2026-07-15-sentinel-sre-copilot-design.md).
Build starts July 20, 2026.

## How it works (once built)
1. The OpenTelemetry Demo runs and streams telemetry into SigNoz (deployed via Foundry).
2. A fault is injected (a `flagd` feature flag) → SigNoz alert fires → webhook to Sentinel.
3. Sentinel gathers correlated evidence via the SigNoz MCP server; Claude forms a root-cause hypothesis.
4. A policy engine chooses auto-heal vs. human-approval (confidence × blast radius).
5. Sentinel applies the fix, then re-queries SigNoz to confirm the signal returned to baseline.
6. Sentinel traces its own decision process into SigNoz and writes an audit trail.

See the design spec for full architecture, scope, and timeline.
