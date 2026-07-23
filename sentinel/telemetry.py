from contextlib import contextmanager
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_initialised = False
tracer = trace.get_tracer("sentinel")

def setup_tracing(service_name: str = "sentinel", otlp_endpoint: str | None = None) -> None:
    global _initialised, tracer
    if _initialised:
        return
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    if otlp_endpoint:
        # imported lazily: keeps plain `import sentinel.telemetry` working without the OTLP exporter
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint)))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer(service_name)
    _initialised = True

@contextmanager
def span(name: str):
    with tracer.start_as_current_span(name) as s:
        yield s
