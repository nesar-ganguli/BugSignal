import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone


request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }
        for field in ("method", "path", "status_code", "duration_ms", "workflow_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    configure_logger(root)


def configure_logger(logger: logging.Logger) -> None:
    if logger.handlers:
        for handler in logger.handlers:
            handler.setFormatter(JsonFormatter())
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
