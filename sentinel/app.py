from fastapi import FastAPI, BackgroundTasks, HTTPException
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
        if incident is None:
            return {"incident_id": None, "status": "ignored"}
        bg.add_task(app.state.orchestrator.handle, incident)
        return {"incident_id": incident.id, "status": incident.status.value}

    @app.post("/incidents/{incident_id}/approve")
    def approve(incident_id: str):
        try:
            inc = app.state.orchestrator.approve(incident_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="no pending incident")
        return {"incident_id": inc.id, "status": inc.status.value}

    @app.get("/incidents/{incident_id}")
    def get_incident(incident_id: str):
        rec = app.state.orchestrator.audit.get(incident_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="unknown incident")
        return rec

    return app

# Real wiring lives behind a factory function so uvicorn constructs it lazily
# (uvicorn sentinel.app:create_app --factory) and importing build_app in tests
# never touches real clients/backends.
def create_app() -> FastAPI:
    import anthropic
    from sentinel.config import get_settings
    from sentinel.signoz_client import get_backend
    from sentinel.policy import load_policy
    from sentinel.actuators import ActuatorRegistry
    from sentinel.actuators.flag import FlagActuator
    from sentinel.audit import AuditStore
    from sentinel.orchestrator import Orchestrator
    from sentinel.telemetry import setup_tracing

    settings = get_settings()
    setup_tracing("sentinel", settings.otlp_endpoint)

    registry = ActuatorRegistry()
    registry.register(FlagActuator(settings.flagd_config_path))

    orchestrator = Orchestrator(
        get_backend(settings),
        anthropic.Anthropic(api_key=settings.anthropic_api_key),
        load_policy("policies/rules.yaml"),
        registry,
        AuditStore(settings.audit_db_path),
        settings.anthropic_model,
    )
    return build_app(orchestrator=orchestrator)
