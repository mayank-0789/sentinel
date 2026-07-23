from sentinel.models import Incident, Evidence

def gather(incident: Incident, backend) -> Evidence:
    w = incident.window
    metric = backend.get_metric(incident.service, incident.signal, w.start, w.end)
    traces = backend.get_traces(incident.service, w.start, w.end)
    logs = backend.get_logs(incident.service, w.start, w.end)
    # scope to the incident's service so blast_radius reflects its own footprint,
    # not the whole-system graph
    topology = {incident.service: backend.get_topology().get(incident.service, [])}
    summary = (f"{incident.service} {incident.signal}={metric} over "
               f"{w.start.isoformat()}..{w.end.isoformat()}; "
               f"{len(traces)} error traces, {len(logs)} error logs.")
    return Evidence(traces=traces, logs=logs, metrics={incident.signal: metric},
                    topology=topology, recent_deploys=[], summary=summary)

def blast_radius(evidence: Evidence) -> int:
    downstream = {svc for deps in evidence.topology.values() for svc in deps}
    return max(1, len(downstream))
