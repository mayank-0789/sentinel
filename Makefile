DEMO_DIR ?= vendor/otel-demo
COMPOSE  ?= docker compose
PY       ?= python

.PHONY: help install test up signoz-up demo-up sentinel-up demo heal verify down clean

help: ## list targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install: ## install Sentinel + dev deps (Python 3.11+)
	$(PY) -m pip install -e '.[dev]'

test: ## unit tests (42)
	$(PY) -m pytest -q

up: signoz-up demo-up sentinel-up ## bring up the whole stack

signoz-up: ## cast + start SigNoz (+ MCP) via Foundry
	foundryctl cast
	$(COMPOSE) -f pours/deployment/compose.yaml up -d

demo-up: ## clone the OTel Demo (if needed), wire it to SigNoz, start it
	@test -d $(DEMO_DIR) || git clone --depth 1 https://github.com/open-telemetry/opentelemetry-demo.git $(DEMO_DIR)
	cp deploy/otelcol-config-extras.yml $(DEMO_DIR)/src/otel-collector/otelcol-config-extras.yml
	$(COMPOSE) -f $(DEMO_DIR)/compose.yaml up -d

sentinel-up: ## build + start Sentinel
	DEMO_DIR=$(DEMO_DIR) $(COMPOSE) up -d --build

demo: ## inject the Scenario-1 fault (trips the alert -> Sentinel heals -> verifies)
	$(PY) scenarios/inject.py $(DEMO_DIR) cartFailure on

heal: ## manually clear the Scenario-1 fault (what FlagActuator does automatically)
	$(PY) scenarios/inject.py $(DEMO_DIR) cartFailure off

verify: test ## unit tests + live stack health
	@curl -sf http://localhost:8080/api/v1/health >/dev/null && echo "SigNoz  healthy" || echo "SigNoz  DOWN"
	@curl -sf http://localhost:9099/healthz     >/dev/null && echo "Sentinel healthy" || echo "Sentinel DOWN"

down: ## tear everything down
	-DEMO_DIR=$(DEMO_DIR) $(COMPOSE) down
	-$(COMPOSE) -f $(DEMO_DIR)/compose.yaml down
	-$(COMPOSE) -f pours/deployment/compose.yaml down

clean: down ## also remove the vendored demo clone
	rm -rf $(DEMO_DIR)
