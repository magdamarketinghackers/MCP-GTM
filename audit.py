import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

AUDIT_FILE = "/tokens/audit.log"


def audit_log(action: str, container_path: str, details: Dict[str, Any], user_id: str = "", dry_run: bool = False):
    """Append a line to the audit log for every write operation."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "container_path": container_path,
        "action": action,
        "dry_run": dry_run,
        "details": details,
    }
    try:
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        with open(AUDIT_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def read_audit_log(lines: int = 50) -> list:
    """Return last N lines from audit log."""
    if not os.path.exists(AUDIT_FILE):
        return []
    try:
        with open(AUDIT_FILE) as f:
            all_lines = f.readlines()
        return [json.loads(l) for l in all_lines[-lines:] if l.strip()]
    except Exception:
        return []
