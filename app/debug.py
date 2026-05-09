"""CLI debug logging helpers."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

LOGGER_NAME = "prefab_db_ui"
REDACTED = "[redacted]"
SENSITIVE_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "password",
    "passwd",
    "secret",
    "token",
)
CONNECTION_IDENTITY_KEYS = {
    "database",
    "database_name",
    "host",
    "mysql_database",
    "mysql_host",
    "mysql_user",
    "user",
    "username",
}


def configure_logging(*, debug: bool) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)

    logger.debug("CLI debug logging enabled.")
    return logger


def log_event(label: str, payload: Any | None = None, *, level: int = logging.INFO) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.log(level, label)
    if payload is not None and logger.isEnabledFor(logging.DEBUG):
        for line in _format_payload(payload):
            logger.log(level, line)


def _format_payload(payload: Any) -> list[str]:
    payload = _redact_payload(payload)
    if isinstance(payload, dict) and "sql" in payload:
        metadata = {key: value for key, value in payload.items() if key != "sql"}
        lines = []
        if metadata:
            lines.append(_to_json(metadata))
        lines.append("SQL:")
        lines.extend(f"  {line}" for line in _format_sql(str(payload["sql"])).splitlines())
        return lines
    return [_to_json(payload)]


def _redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            key_text = str(key)
            if _should_redact_key(key_text):
                redacted[key] = REDACTED if item else item
            else:
                redacted[key] = _redact_payload(item)
        return redacted
    if isinstance(value, list):
        return [_redact_payload(item) for item in value]
    return value


def _should_redact_key(key: str) -> bool:
    normalized = key.lower()
    return normalized in CONNECTION_IDENTITY_KEYS or any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def _format_sql(sql: str) -> str:
    formatted = sql.replace("\\n", "\n").strip()
    if "\n" in formatted:
        return formatted

    replacements = [
        (r"\s+UNION\s+ALL\s+", "\nUNION ALL\n"),
        (r"\s+UNION(?!\s+ALL)\s+", "\nUNION\n"),
        (r"\s+FROM\s+", "\nFROM "),
        (r"\s+LEFT\s+JOIN\s+", "\nLEFT JOIN "),
        (r"\s+RIGHT\s+JOIN\s+", "\nRIGHT JOIN "),
        (r"\s+INNER\s+JOIN\s+", "\nINNER JOIN "),
        (r"\s+JOIN\s+", "\nJOIN "),
        (r"\s+WHERE\s+", "\nWHERE "),
        (r"\s+GROUP\s+BY\s+", "\nGROUP BY "),
        (r"\s+ORDER\s+BY\s+", "\nORDER BY "),
        (r"\s+LIMIT\s+", "\nLIMIT "),
    ]
    for pattern, replacement in replacements:
        formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
    return formatted


def _to_json(payload: Any) -> str:
    try:
        return json.dumps(payload, indent=2, sort_keys=True, default=str)
    except TypeError:
        return str(payload)
