import json
import os
from datetime import datetime, timezone


RUN_LOG = []


def log_entry(role: str, content: str, meta: dict | None = None):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "content": content,
    }
    if meta:
        entry["meta"] = meta
    RUN_LOG.append(entry)


def dump_log():
    return "\n".join(json.dumps(e) for e in RUN_LOG)
