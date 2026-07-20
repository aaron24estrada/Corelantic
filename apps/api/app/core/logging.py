"""Structured JSON logging with a per-request id.

Every log line is one JSON object carrying the current request id (from a context var
set by the request middleware), so logs correlate across a request without threading an
id through every call. Extra fields passed via ``logger.info(..., extra={...})`` are
merged into the object.
"""

import json
import logging
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

# Standard LogRecord attributes, so the formatter can tell apart caller-supplied extras.
_RESERVED = set(vars(logging.makeLogRecord({}))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


# The azure-core pipeline logs every HTTP response — including a full header dump — at INFO,
# several times per token refresh. That buries our own lines, and in particular the device-code
# sign-in prompt a developer has to read and act on. Warnings and errors still come through.
_NOISY_LOGGERS = (
    "azure.core.pipeline.policies.http_logging_policy",
    "azure.identity",
    "msal",
)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
