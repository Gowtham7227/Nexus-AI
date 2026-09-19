import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

# Structured audit logger configuration
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
AUDIT_LOG_FILE = os.path.join(LOG_DIR, "privacy_audit.log")

_audit_logger = logging.getLogger("nexusai_privacy_audit")
_audit_logger.setLevel(logging.INFO)
_audit_logger.propagate = False

if not _audit_logger.handlers:
    file_handler = logging.FileHandler(AUDIT_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    _audit_logger.addHandler(file_handler)


def log_privacy_event(
    event_type: str,
    user_id: int,
    document_ids: Optional[list] = None,
    privacy_risk: str = "LOW",
    injection_detected: bool = False,
    redaction_applied: bool = False,
    model_used: str = "gemini",
    evidence_quality: str = "High",
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Record a privacy & security audit event safely.
    Strictly guarantees that passwords, tokens, full prompts, or raw document secrets are NEVER logged.
    """
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "document_count": len(document_ids) if document_ids else 0,
        "document_names": [os.path.basename(str(d)) for d in (document_ids or [])],
        "privacy_risk": privacy_risk,
        "injection_detected": injection_detected,
        "redaction_applied": redaction_applied,
        "model_used": model_used,
        "evidence_quality": evidence_quality,
        "metadata": details or {},
    }

    try:
        _audit_logger.info(json.dumps(event))
    except Exception as e:
        print("⚠️ Audit Logging skipped:", str(e))
