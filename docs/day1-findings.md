# Day-1 findings — live-stack de-risk

Captured against the real running stack (not assumptions). These reconcile the code and spec with
how SigNoz, the OTel Demo, and flagd actually behave in this deployment.

## 1. SigNoz

- **Version:** `v0.134.0` (EE build), deployed via Foundry (`casting.yaml` → `pours/deployment/compose.yaml`).
- **Endpoints:** UI/API on `:8080`, OTLP ingest on `:4317` (gRPC) / `:4318` (HTTP), MCP server on `:8000`.
- **First-run setup required:** a fresh instance reports `{"setupCompleted": false}` at
  `GET /api/v1/version`. An admin user must be created before the query API is usable.
- **Query API needs auth:** `POST /api/v3/query_range` and `/api/v4/query_range` return **401** without
  credentials. Authenticated access uses a `SIGNOZ-API-KEY` header (create a key in the SigNoz UI:
  Settings → API Keys) or a session JWT.
  - **Code impact:** `sentinel/signoz_client.py::QueryApiBackend` must send the API key header and target
    a versioned endpoint (`/api/v3/query_range`). Tracked and fixed alongside these findings.

## 2. OpenTelemetry Demo

- Standard OTel Demo (astronomy shop, ~15+ services + load generator).
- **Wiring to SigNoz:** the demo's own collector (`otel-collector`) fans telemetry out; add a SigNoz OTLP
  exporter via `src/otel-collector/otelcol-config-extras.yml` (merged into the main config) pointing at
  the SigNoz ingester. No changes to the demo services themselves.

## 3. flagd chaos flags (verified against `src/flagd/demo.flagd.json`)

The flag **keys** differ from the original spec guesses — these are the real ones in the pulled demo:

| Scenario | Real flag key | Symptom | Policy path |
|---|---|---|---|
| 1 — auto-heal (low risk) | `cartFailure` | cart/checkout errors | auto-heal (disable flag) |
| 2 — auto w/ guard | `paymentFailure`, `paymentUnreachable` | payment step fails | auto with guard |
| 3 — human approval | `adHighCpu`, `recommendationCacheFailure` | latency / CPU / cache storm | human approval |

Other available fault flags: `adFailure`, `adManualGc`, `emailMemoryLeak`, `failedReadinessProbe`,
`imageSlowLoad`, `intlShippingSlowdown`, `kafkaQueueProblems`, `productCatalogFailure`.

- **Toggle mechanism:** edit the flag's `defaultVariant` in `src/flagd/demo.flagd.json`
  (`"off"` → `"on"` to inject the fault; back to `"off"` to remediate). flagd watches the file and
  hot-reloads — no restart needed. This is what `FlagActuator` automates.

## 4. SigNoz MCP server

- Running on `:8000` (streamable-HTTP transport; `GET /` returns 404, which is expected — it routes at
  the MCP path, not root). Full tool catalog is enumerated via an MCP `initialize` + `tools/list`
  handshake; `McpBackend` is the alternate evidence backend behind the same `SignozBackend` interface.
- The default evidence backend is `query_api` (the complete, auth'd REST seam); MCP is the swap-in
  alternative and does not gate the core loop.

## 5. Alert webhook payload

- SigNoz alert rules route to a **webhook notification channel** (Settings → Alert Channels → Webhook).
- The webhook POSTs a JSON body per firing alert; `sentinel/detector.py` normalizes it into an
  `Incident`. The exact field paths are confirmed by pointing a test channel at the detector and
  tripping a rule.
