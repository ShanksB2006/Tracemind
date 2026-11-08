from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import json


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    timestamp: str
    service: str
    level: LogLevel
    message: str
    trace_id: str
    span_id: str
    latency_ms: float
    status_code: int
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_formatted_line(self) -> str:
        """Standard human-readable log line with structured metadata."""
        return (
            f"{self.timestamp} [{self.level.value:<8}] [{self.service}] "
            f"[trace={self.trace_id} span={self.span_id}] "
            f"status={self.status_code} latency={self.latency_ms:.1f}ms - {self.message}"
        )

    def to_json(self) -> str:
        data = asdict(self)
        data["level"] = self.level.value
        return json.dumps(data)


@dataclass
class ServiceNode:
    name: str
    tier: str  # gateway, business, persistence, etc.
    dependencies: list[str] = field(default_factory=list)
