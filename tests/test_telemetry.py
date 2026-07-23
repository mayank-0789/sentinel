from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sentinel import telemetry

def test_span_records_to_provider():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    telemetry.tracer = trace.get_tracer("sentinel")
    with telemetry.span("detect"):
        pass
    names = [s.name for s in exporter.get_finished_spans()]
    assert "detect" in names
