"""FastAPI router for TraceMind incidents, topology, telemetry, and chaos simulation."""
from __future__ import annotations
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from chaos_generator.topology import ServiceTopology
from chaos_generator.scenarios import PaymentDBExhaustionScenario, MemoryLeakScenario
from ..ingestion.parser import LogIngestionEngine, ParsedLog
from ..ingestion.windowing import FeatureWindowExtractor, WindowMetrics
from ..ml.anomaly_service import StreamingAnomalyService
from ..ml.autoencoder_model import BottleneckAutoencoder
from ..rca.causal_engine import CausalRCAEngine, RootCauseReport
from ..rca.topology_graph import TopologyGraph
from ..agents.investigator import MultiAgentInvestigator, IncidentInvestigationReport


router = APIRouter(prefix="/api/v1")

# Global state store for demo session
INCIDENTS_DB: Dict[str, IncidentInvestigationReport] = {}
TIMELINE_DB: List[Dict[str, Any]] = []
LOGS_CACHE: List[Dict[str, Any]] = []


class SimulateRequest(BaseModel):
    scenario: str = "payment_db_exhaustion"
    duration_seconds: int = 60


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "TraceMind AIOps Platform", "version": "1.0.0"}


@router.post("/chaos/simulate")
def trigger_simulation(req: SimulateRequest):
    """Triggers realistic microservice chaos and runs the end-to-end detection & RCA pipeline."""
    topology = ServiceTopology()
    if req.scenario == "payment_db_exhaustion":
        scenario = PaymentDBExhaustionScenario(topology)
    elif req.scenario == "memory_leak":
        scenario = MemoryLeakScenario(topology)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {req.scenario}")

    # Generate logs
    engine = LogIngestionEngine()
    parsed_logs: List[ParsedLog] = []

    for tick in range(req.duration_seconds):
        raw_entries = scenario.generate_tick(tick, req.duration_seconds)
        for e in raw_entries:
            parsed = engine.parse_line(e.to_formatted_line())
            if parsed:
                parsed_logs.append(parsed)

    # Windowing
    extractor = FeatureWindowExtractor(window_size_seconds=2.0)
    windows = extractor.extract_windows(parsed_logs)

    # Store timeline
    global TIMELINE_DB, LOGS_CACHE
    TIMELINE_DB = [
        {
            "window_index": w.window_index,
            "timestamp": w.end_time,
            "error_rate": round(w.error_ratio * 100, 1),
            "avg_latency": round(w.avg_latency_ms, 1),
            "p95_latency": round(w.p95_latency_ms, 1),
            "total_logs": w.total_logs,
            "error_count": w.error_count
        }
        for w in windows
    ]
    LOGS_CACHE = [l.to_dict() for l in parsed_logs[-100:]]

    # Filter anomalous logs
    err_logs = [l for l in parsed_logs if l.level in ("ERROR", "CRITICAL", "WARN") or l.latency_ms > 1000]

    if not err_logs:
        return {"status": "success", "message": "Simulation ran with 0 anomalies detected."}

    # Execute Causal RCA
    incident_id = f"inc_{uuid.uuid4().hex[:8]}"
    rca_engine = CausalRCAEngine()
    rca_report = rca_engine.analyze(incident_id, err_logs)

    # Execute Multi-Agent Investigation & RAG Synthesis
    investigator = MultiAgentInvestigator()
    incident_report = investigator.investigate(rca_report, err_logs)

    INCIDENTS_DB[incident_id] = incident_report

    return {
        "status": "incident_detected",
        "incident": incident_report.to_dict()
    }


@router.get("/incidents")
def list_incidents():
    return list(INCIDENTS_DB.values())


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    if incident_id not in INCIDENTS_DB:
        raise HTTPException(status_code=404, detail="Incident not found")
    return INCIDENTS_DB[incident_id].to_dict()


@router.get("/topology")
def get_topology():
    graph = TopologyGraph.create_default()
    nodes = []
    edges = []

    for name, node in graph.nodes.items():
        nodes.append({
            "id": name,
            "label": name,
            "tier": node.tier
        })
        for target in node.downstream:
            edges.append({
                "source": name,
                "target": target
            })

    return {"nodes": nodes, "edges": edges}


@router.get("/metrics/timeline")
def get_timeline():
    return TIMELINE_DB


@router.get("/logs/recent")
def get_recent_logs(limit: int = 50):
    return LOGS_CACHE[-limit:]


@router.get("/benchmarks")
def get_benchmarks():
    bench_file = Path(__file__).resolve().parent.parent.parent.parent / "benchmarks" / "benchmark_results.json"
    if bench_file.exists():
        with open(bench_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"message": "Run python benchmarks/run_benchmark.py to generate benchmarks."}
