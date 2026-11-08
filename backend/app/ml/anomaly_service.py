"""Streaming Anomaly Detection Service.

Continuously scores incoming telemetry windows and dispatches structured alerts.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
import numpy as np

from .base import BaseAnomalyDetector
from .isolation_forest_model import IsolationForestDetector
from .autoencoder_model import BottleneckAutoencoder
from ..ingestion.windowing import WindowMetrics, FeatureWindowExtractor
from ..ingestion.parser import ParsedLog


@dataclass
class AnomalyAlert:
    alert_id: str
    timestamp: str
    model_used: str
    anomaly_score: float
    severity: str  # CRITICAL, HIGH, WARNING
    window_index: int
    top_affected_services: List[str]
    suspected_events: List[str]
    window_summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StreamingAnomalyService:
    """Manages active anomaly detection models and evaluates incoming telemetry windows."""

    def __init__(self, detector: Optional[BaseAnomalyDetector] = None):
        self.detector = detector or IsolationForestDetector()
        self.all_event_ids: List[str] = []
        self.active_alerts: List[AnomalyAlert] = []

    def calibrate_on_baseline(self, baseline_windows: List[WindowMetrics], all_event_ids: List[str]):
        """Calibrates detector on nominal baseline telemetry."""
        self.all_event_ids = all_event_ids
        X_train = np.array([w.to_feature_vector(all_event_ids) for w in baseline_windows], dtype=np.float32)
        self.detector.fit(X_train)

    def evaluate_window(self, window: WindowMetrics) -> Optional[AnomalyAlert]:
        """Evaluates a single time window. Returns AnomalyAlert if anomalous."""
        feat = np.array([window.to_feature_vector(self.all_event_ids)], dtype=np.float32)
        score = float(self.detector.score_samples(feat)[0])
        is_anomaly = bool(self.detector.predict(feat)[0] == 1 or score > 0.65)

        if not is_anomaly:
            return None

        # Determine severity
        if score > 0.85 or window.error_ratio > 0.4:
            severity = "CRITICAL"
        elif score > 0.70 or window.error_ratio > 0.15:
            severity = "HIGH"
        else:
            severity = "WARNING"

        # Identify services with highest latency or errors
        sorted_services = sorted(
            window.service_stats.items(),
            key=lambda item: (item[1].get("errors", 0), item[1].get("avg_latency", 0)),
            reverse=True
        )
        affected_services = [s[0] for s in sorted_services[:3]]

        # Identify dominant event IDs in this anomalous window
        sorted_events = sorted(window.event_counts.items(), key=lambda item: item[1], reverse=True)
        top_events = [e[0] for e in sorted_events[:4]]

        alert = AnomalyAlert(
            alert_id=f"alt_{uuid.uuid4().hex[:8]}",
            timestamp=window.end_time,
            model_used=self.detector.name,
            anomaly_score=round(score, 4),
            severity=severity,
            window_index=window.window_index,
            top_affected_services=affected_services,
            suspected_events=top_events,
            window_summary={
                "total_logs": window.total_logs,
                "error_count": window.error_count,
                "error_ratio": round(window.error_ratio, 4),
                "avg_latency_ms": round(window.avg_latency_ms, 2),
                "max_latency_ms": round(window.max_latency_ms, 2),
                "p95_latency_ms": round(window.p95_latency_ms, 2)
            }
        )

        self.active_alerts.append(alert)
        return alert
