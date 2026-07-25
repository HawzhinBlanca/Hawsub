import logging
import json
import sys
from typing import Any, Dict, Optional

class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON logging."""
    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "project_id"):
            log_entry["project_id"] = getattr(record, "project_id")
        if hasattr(record, "stage"):
            log_entry["stage"] = getattr(record, "stage")
        if hasattr(record, "scene_id"):
            log_entry["scene_id"] = getattr(record, "scene_id")
        if hasattr(record, "provider"):
            log_entry["provider"] = getattr(record, "provider")
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str = "hawsub", level: int = logging.INFO, json_format: bool = False) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        if json_format:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"))
        logger.addHandler(handler)
    return logger
