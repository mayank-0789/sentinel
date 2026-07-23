import json, sqlite3, threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from sentinel.models import Incident

def _enc(o):
    if is_dataclass(o) and not isinstance(o, type):
        return _enc(asdict(o))
    if isinstance(o, dict):
        return {k: _enc(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_enc(v) for v in o]
    if isinstance(o, Enum):
        return o.value
    if isinstance(o, datetime):
        return o.isoformat()
    return o

class AuditStore:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, doc TEXT)")
        self.db.commit()
        self._lock = threading.Lock()

    def record(self, incident: Incident, hypothesis=None, decision=None,
               remediation=None, verification=None, error=None):
        with self._lock:
            cur = self._get(incident.id) or {}
            cur.update({"id": incident.id, "service": incident.service,
                        "signal": incident.signal, "status": incident.status.value})
            for key, val in [("hypothesis", hypothesis), ("decision", decision),
                             ("remediation", remediation), ("verification", verification),
                             ("error", error)]:
                if val is not None:
                    cur[key] = _enc(val)
            self.db.execute("INSERT INTO incidents(id, doc) VALUES(?,?) "
                            "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc",
                            (incident.id, json.dumps(cur)))
            self.db.commit()

    def get(self, incident_id: str):
        with self._lock:
            return self._get(incident_id)

    def _get(self, incident_id: str):
        row = self.db.execute("SELECT doc FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return json.loads(row[0]) if row else None
