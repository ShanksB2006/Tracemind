"""Time-series windowing and feature vector extraction for ML Anomaly Detection."""
from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from .parser import ParsedLog


@dataclass
class WindowMetrics:
    window_index: int
    start_time: str
    end_time: str
    total_logs: int = 0
    error_count: int = 0
    warn_count: int = 0
    error_ratio: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    service_stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    event_counts: Dict[str, int] = field(default_factory=dict)

    def to_feature_vector(self, all_event_ids: List[str]) -> List[float]:
        """Converts window metrics into a numerical feature vector for ML models."""
        features = [
            float(self.total_logs),
            float(self.error_count),
            float(self.warn_count),
            float(self.error_ratio),
            float(self.avg_latency_ms),
            float(self.max_latency_ms),
            float(self.p95_latency_ms),
        ]
        # Append template frequency vector (TF of event IDs)
        for eid in all_event_ids:
            features.append(float(self.event_counts.get(eid, 0)))
        return features


class FeatureWindowExtractor:
    """Aggregates parsed logs into discrete time windows and computes statistical features."""

    def __init__(self, window_size_seconds: float = 5.0):
        self.window_size_seconds = window_size_seconds

    def _parse_timestamp(self, ts_str: str) -> Optional[datetime]:
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                pass
        return None

    def extract_windows(self, logs: List[ParsedLog]) -> List[WindowMetrics]:
        if not logs:
            return []

        # Sort logs by timestamp if available
        valid_logs = [log for log in logs if log.timestamp]
        if not valid_logs:
            return []

        windows: List[WindowMetrics] = []
        first_dt = self._parse_timestamp(valid_logs[0].timestamp)
        if not first_dt:
            return []

        window_start_dt = first_dt
        window_idx = 0
        current_logs: List[ParsedLog] = []

        for log in valid_logs:
            log_dt = self._parse_timestamp(log.timestamp)
            if not log_dt:
                continue

            delta_sec = (log_dt - window_start_dt).total_seconds()

            if delta_sec >= self.window_size_seconds:
                # Close current window
                if current_logs:
                    windows.append(self._compute_window_metrics(window_idx, current_logs))
                    window_idx += 1
                    current_logs = []
                # Advance window start
                window_start_dt = log_dt

            current_logs.append(log)

        # Close final window
        if current_logs:
            windows.append(self._compute_window_metrics(window_idx, current_logs))

        return windows

    def _compute_window_metrics(self, idx: int, window_logs: List[ParsedLog]) -> WindowMetrics:
        total = len(window_logs)
        errors = sum(1 for l in window_logs if l.level in ("ERROR", "CRITICAL"))
        warns = sum(1 for l in window_logs if l.level == "WARN")
        latencies = [l.latency_ms for l in window_logs]

        latencies.sort()
        avg_lat = sum(latencies) / max(1, total)
        max_lat = latencies[-1] if latencies else 0.0
        p95_idx = int(0.95 * total)
        p95_lat = latencies[min(p95_idx, total - 1)] if latencies else 0.0

        # Service-specific metrics
        services = set(l.service for l in window_logs)
        svc_stats: Dict[str, Dict[str, float]] = {}
        for svc in services:
            svc_logs = [l for l in window_logs if l.service == svc]
            svc_errs = sum(1 for l in svc_logs if l.level in ("ERROR", "CRITICAL"))
            svc_lats = [l.latency_ms for l in svc_logs]
            svc_avg_lat = sum(svc_lats) / max(1, len(svc_lats))
            svc_stats[svc] = {
                "count": float(len(svc_logs)),
                "errors": float(svc_errs),
                "avg_latency": svc_avg_lat
            }

        # Event ID frequencies
        event_counts: Dict[str, int] = {}
        for l in window_logs:
            event_counts[l.event_id] = event_counts.get(l.event_id, 0) + 1

        return WindowMetrics(
            window_index=idx,
            start_time=window_logs[0].timestamp,
            end_time=window_logs[-1].timestamp,
            total_logs=total,
            error_count=errors,
            warn_count=warns,
            error_ratio=errors / max(1, total),
            avg_latency_ms=avg_lat,
            max_latency_ms=max_lat,
            p95_latency_ms=p95_lat,
            service_stats=svc_stats,
            event_counts=event_counts
        )
