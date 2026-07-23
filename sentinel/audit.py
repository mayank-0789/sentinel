import json, sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime
from sentinel.models import Incident

def _enc(o):
    if is_dataclass(o):
        return {k: _enc(v) for k, v in asdict(o).items()}
    if isinstance(o, datetime):
        return o.isoformat()
    return o

class AuditStore:
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self.db.execute("CREATE TABLE IF NOT EXISTS incidents (id TEXT PRIMARY KEY, doc TEXT)")
        self.db.commit()

    def record(self, incident: Incident, hypothesis=None, decision=None,
               remediation=None, verification=None):
        cur = self.get(incident.id) or {}
        cur.update({"id": incident.id, "service": incident.service,
                    "signal": incident.signal, "status": incident.status.value})
        for key, val in [("hypothesis", hypothesis), ("decision", decision),
                         ("remediation", remediation), ("verification", verification)]:
            if val is not None:
                cur[key] = _enc(val)
        self.db.execute("INSERT INTO incidents(id, doc) VALUES(?,?) "
                        "ON CONFLICT(id) DO UPDATE SET doc=excluded.doc",
                        (incident.id, json.dumps(cur)))
        self.db.commit()

    def get(self, incident_id: str):
        row = self.db.execute("SELECT doc FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return json.loads(row[0]) if row else None
