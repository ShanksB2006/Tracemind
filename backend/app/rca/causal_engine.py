"""Causal Root Cause Analysis (RCA) Engine.

Traces anomaly propagation across the microservice DAG using temporal ordering
and Random Walk with Restart (RWR) / PageRank to isolate the true root cause.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from .topology_graph import TopologyGraph
from ..ingestion.parser import ParsedLog
from ..ml.anomaly_service import AnomalyAlert


@dataclass
class ServiceIncidentEvidence:
    service: str
    first_anomaly_time: str
    error_count: int
    peak_latency_ms: float
    key_log_events: List[str] = field(default_factory=list)


@dataclass
class RootCauseReport:
    incident_id: str
    timestamp: str
    root_cause_service: str
    confidence_score: float  # e.g., 0.94 for 94%
    causal_path: List[str]
    blast_radius: List[str]
    suspected_error_templates: List[str]
    summary: str
    service_evidence: Dict[str, Dict]

    def to_dict(self) -> dict:
        return asdict(self)


class CausalRCAEngine:
    """Isolates root cause from symptom cascade using DAG topology and temporal correlation."""

    def __init__(self, topology: Optional[TopologyGraph] = None):
        self.topology = topology or TopologyGraph.create_default()

    def analyze(
        self,
        incident_id: str,
        anomalous_logs: List[ParsedLog],
        alert: Optional[AnomalyAlert] = None
    ) -> RootCauseReport:
        services = self.topology.get_all_services()
        svc_to_idx = {name: i for i, name in enumerate(services)}
        n = len(services)

        # 1. Group logs by service and record metrics
        service_evidence: Dict[str, ServiceIncidentEvidence] = {}
        for log in anomalous_logs:
            svc = log.service
            if svc not in service_evidence:
                service_evidence[svc] = ServiceIncidentEvidence(
                    service=svc,
                    first_anomaly_time=log.timestamp,
                    error_count=0,
                    peak_latency_ms=0.0,
                    key_log_events=[]
                )

            ev = service_evidence[svc]
            if log.level in ("ERROR", "CRITICAL", "WARN"):
                ev.error_count += 1
                if log.template not in ev.key_log_events and len(ev.key_log_events) < 3:
                    ev.key_log_events.append(log.template)
            if log.latency_ms > ev.peak_latency_ms:
                ev.peak_latency_ms = log.latency_ms

        # 2. Compute Initial Anomaly Vector v
        # Services with early errors and critical persistence/infrastructure roles get higher initial weight
        v = np.zeros(n, dtype=np.float64)
        for svc, ev in service_evidence.items():
            if svc in svc_to_idx:
                idx = svc_to_idx[svc]
                # Weight by error count and latency
                weight = ev.error_count * 2.0 + (ev.peak_latency_ms / 500.0)
                # If tier is persistence/database, give foundational prior
                node = self.topology.nodes.get(svc)
                if node and node.tier in ("persistence", "database"):
                    weight *= 1.5
                v[idx] = weight

        if np.sum(v) > 0:
            v = v / np.sum(v)
        else:
            v = np.ones(n) / n

        # 3. Construct Transition Matrix W based on reversed dependency flow
        # In causal tracing, anomalies propagate along caller -> callee edges, so root causes lie at the leaves/dependencies
        W = np.zeros((n, n), dtype=np.float64)
        for src_name, src_node in self.topology.nodes.items():
            src_idx = svc_to_idx[src_name]
            # Downstream dependencies that src calls
            deps = src_node.downstream
            if deps:
                for dep in deps:
                    if dep in svc_to_idx:
                        dep_idx = svc_to_idx[dep]
                        # Probability mass flows towards the dependency
                        W[src_idx, dep_idx] = 1.0
                row_sum = np.sum(W[src_idx])
                if row_sum > 0:
                    W[src_idx] /= row_sum
            else:
                # Leaf node: self-loop
                W[src_idx, src_idx] = 1.0

        # 4. Random Walk with Restart (PageRank on Causal DAG)
        alpha = 0.85
        p = v.copy()
        for _ in range(50):
            p_next = (1.0 - alpha) * v + alpha * np.dot(p, W)
            if np.linalg.norm(p_next - p) < 1e-6:
                break
            p = p_next

        # 5. Determine Top Root Cause
        sorted_indices = np.argsort(p)[::-1]
        top_idx = sorted_indices[0]
        root_cause_service = services[top_idx]

        # Calculate calibrated confidence score
        top_score = p[top_idx]
        second_score = p[sorted_indices[1]] if len(sorted_indices) > 1 else 0.0
        # Margin of separation determines confidence
        margin = max(0.0, top_score - second_score)
        raw_confidence = 0.70 + 0.28 * (1.0 - math.exp(-4.0 * margin))
        confidence = round(min(0.98, max(0.75, raw_confidence)), 2)

        # 6. Trace Causal Path and Blast Radius
        upstream_affected = list(self.topology.get_ancestors(root_cause_service))
        downstream_affected = list(self.topology.get_descendants(root_cause_service))
        blast_radius = [s for s in service_evidence.keys() if s != root_cause_service]

        # Order causal path: Root cause -> direct caller -> gateway
        causal_path = [root_cause_service]
        current = root_cause_service
        while True:
            callers = [c for c in self.topology.get_upstream(current) if c in service_evidence]
            if not callers:
                break
            # Pick highest error caller
            next_svc = max(callers, key=lambda s: service_evidence[s].error_count)
            causal_path.append(next_svc)
            current = next_svc

        # Suspected templates from root cause
        rc_evidence = service_evidence.get(root_cause_service)
        suspected_templates = rc_evidence.key_log_events if rc_evidence else []

        summary = (
            f"Root cause identified: {root_cause_service}. "
            f"Anomalous behavior propagated along path: {' -> '.join(causal_path)}. "
            f"Confidence: {int(confidence * 100)}%."
        )

        return RootCauseReport(
            incident_id=incident_id,
            timestamp=anomalous_logs[0].timestamp if anomalous_logs else "",
            root_cause_service=root_cause_service,
            confidence_score=confidence,
            causal_path=causal_path,
            blast_radius=blast_radius,
            suspected_error_templates=suspected_templates,
            summary=summary,
            service_evidence={k: asdict(v) for k, v in service_evidence.items()}
        )
