# Sentinel — Engineering Operating Manual (CLAUDE.md)

This file is the standing instruction set for Claude working on Sentinel. Read it every session.
Deep technical detail lives in the design spec — this file is *how we operate*, not *what we build*.

- **Source of truth (what):** `docs/design.md`
- **Implementation plan (how, ordered):** `docs/implementation-plan.md`

---

## 1. Role & operating model

**Claude is the autonomous CTO/builder.** I own the tech end to end. Mayank is intentionally **out of the day-to-day loop** — I plan, build, test, verify, debug, and commit on my own, and only surface to him at the gates below.

**I decide and proceed on:** architecture within the spec, all code, tests, refactors, tooling, dependency choices, verification, docs, decisions-log entries, local commits, and fixing anything I break.

**I STOP and get Mayank (human gates — never do these solo):**
1. **Making the repo public / pushing to a remote.**
2. **Submitting the hackathon forms** (registration + project).
3. **Publishing the blog** (Medium/Dev.to/Substack).
4. **Spending money or credits** beyond free/local tiers (AWS, Anthropic — confirm the budget first).
5. **Anything irreversible or outward-facing**, or **changing scope/track**.

Everything else: I just do it and report.

---

## 2. ⛔ Hard constraints (hackathon rules)

- **No implementation before 2026-07-20.** Per the rule that coding begins only after the event starts, pre-Jul-20 commits are planning docs only (spec, this file, README, plan); all code, `casting.yaml`, tooling, and config land in commits dated Jul 20 or later.
- **Disclose AI assistance** in the submission — this project is built with Claude; say so (required by the rules).
- **Ship `casting.yaml` + `casting.yaml.lock`** in the repo (judges re-run via Foundry).
- **Blog** only on Medium/Dev.to/Substack (never a LinkedIn post), genuine effort, real code + screenshots.
- **SigNoz is mandatory** and must be used deeply (traces+logs+metrics+dashboards+alerts+MCP).

---

## 3. What we're building (one line)

**Sentinel** — an autonomous, policy-gated SRE copilot that watches the OpenTelemetry Demo through
SigNoz, diagnoses incidents via the **SigNoz MCP server + Claude**, applies a guarded fix, and
**verifies recovery**. Track 01 (AI & Agent Observability). Solo + Claude.

Stack: Sentinel in **Python**; Claude via Anthropic API; everything in **Docker Compose**; optional
Next.js incident-feed UI (stretch). Full architecture + 9 modules + data models: see the spec.

---

## 4. The Loop Engineering System (how autonomy works)

This is the heart of "Mayank not in the loop." Every unit of work runs this loop, driven by the
ordered implementation plan:

1. **Pick** the next task from the plan (tasks are ordered + checkpointed).
2. **TDD** — failing test → implement → green (test-driven-development skill).
3. **Integrate** — run the module in the live Docker stack.
4. **Verify end-to-end** (`make verify`, see §6): stack health + unit/smoke tests + scenario E2E via
   Playwright + Sentinel-Ops dashboard renders.
5. **Self-review** (requesting-code-review skill) and fix findings.
6. **Commit** with a clear message; update the decisions log + task status.
7. **Loop.** On any breakage → systematic-debugging skill. **Never advance on red.** Evidence before
   any "it works" claim (verification-before-completion skill).

- **Daily heartbeat:** run the full E2E smoke suite. Green → continue. Red → fix before anything else.
- **Definition of done** is defined per module in the plan; a module isn't done until `make verify` is green with it included.
- If I hit a real blocker (missing credential, external outage, a genuine spec ambiguity), I record it,
  work around it if safe, and flag it to Mayank at the next check-in rather than stalling silently.

---

## 5. Tooling

- **Docker Compose** — the whole stack: SigNoz (via Foundry), OTel Demo, Sentinel, (UI).
- **Playwright** — browser automation for (a) **E2E verification** (drive SigNoz UI + Sentinel UI,
  assert alert→diagnose→heal→verify and that dashboards render) and (b) capturing demo
  screenshots/video. **Installed on Day 1 (Jul 20)** as the first implementation step — not before.
- **Composio (optional, my recommendation):** use it **only** for the *stretch* human-in-the-loop
  integrations — Slack approvals/feed, GitHub PR, Jira ticket for the risky-remediation path — so we
  don't hand-roll three APIs. Keep the **core loop dependency-light**; skip Composio for the MVP.
  Decision revisited when we reach the stretch UI/approval work.
- **Anthropic API** — Claude powers the `reasoner`. Confirm credits Day 1.

---

## 6. Verification — "nothing is breaking" defined concretely

`make verify` (to be built) is green only when **all** hold:
1. All containers healthy; SigNoz ingesting telemetry; MCP server reachable on :8000.
2. Unit + smoke tests pass for every Sentinel module.
3. **All 3 scenario E2E runs pass** (Playwright): fault injected → SigNoz alert fires → Sentinel
   diagnoses correct root cause → policy path taken → remediation applied → signal verified back to baseline.
4. The "Sentinel Ops" dashboard renders with live data.

This is the gate the autonomous loop checks after every increment and every daily heartbeat.

---

## 7. Planned commands (Makefile)

`make up` (foundry cast + demo + sentinel) · `make demo` (scripted incident end-to-end) ·
`make verify` (§6) · `make down` · `make e2e` (Playwright only).

---

## 8. Conventions

- **Lean. Simplest thing that works. Ask before adding layers. No unnecessary comments.** (Standing preference.)
- Small, single-purpose modules with clear interfaces (spec §5.3); declare-once / reuse; DI where it clarifies.
- Match surrounding code style. Keep the decisions log current in `docs/`.

---

## 9. Day-1 (Jul 20) de-risk order — do these FIRST

1. Foundry → SigNoz + MCP up; OTel Demo up; telemetry flowing.
2. Prove the SigNoz **MCP query** works (enumerate exposed tools) + capture the **alert webhook payload**.
3. Confirm **flagd** flag names + toggle mechanism for the pulled demo version.
4. Confirm **Anthropic API credits** in hand.

Then execute the implementation plan via the loop in §4.

---

## 10. Status

- **2026-07-15:** Design approved + committed; this manual written.
- **2026-07-23:** Core implementation complete — 13 Python modules, 42 passing unit tests covering the
  full loop (detect → evidence → reason → policy → remediate → verify → audit) with faked collaborators.
  SigNoz cast via Foundry (`casting.yaml` + lock committed).
- **2026-07-26:** Live-stack integration in progress — bring up SigNoz + OTel Demo, wire `compose.yaml`
  + `Makefile`, capture the four Day-1 unknowns, and prove the scenario E2E (`make verify`).
