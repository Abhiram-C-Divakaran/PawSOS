import json
import logging
import re
from datetime import datetime
from typing import Any, Dict

SENSITIVE_PATTERNS = [
    re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE),
    re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE),
    re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE),
    re.compile(r'key["\']?\s*[:=]\s*["\']?([^"\'\s]+)', re.IGNORECASE),
]

def sanitize_message(msg: str) -> str:
    """Mask credentials, tokens, and secrets from log strings."""
    if not isinstance(msg, str):
        return str(msg)
    sanitized = msg
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub(r'***REDACTED***', sanitized)
    return sanitized

class JSONLogFormatter(logging.Formatter):
    """Structured JSON formatter with request and context metadata."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_message(record.getMessage()),
        }

        # Extract structured event metadata if present
        for field in ["event", "request_id", "user_id", "case_id", "offer_id", "status_code"]:
            val = getattr(record, field, None)
            if val is not None:
                log_entry[field] = str(val)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)

def setup_logging():
    """Configure root logger with structured formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONLogFormatter())
    logging.root.handlers = [handler]
    logging.root.setLevel(logging.INFO)
