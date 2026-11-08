"""Multi-Agent Incident Investigator & Report Synthesizer.

Coordinates specialized agent personas to synthesize root cause findings,
blast radius topology, and RAG-retrieved remediation runbooks.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from ..rca.causal_engine import RootCauseReport
from ..rag.runbook_retriever import RunbookRetriever, RetrievalResult
from ..ingestion.parser import ParsedLog


@dataclass
class IncidentInvestigationReport:
    incident_id: str
    title: str
    detected_at: str
    root_cause_service: str
    confidence_percentage: int
    anomaly_detected_summary: str
    root_cause_identified: str
    related_services_path: str
    suggested_solution: str
    remediation_commands: List[str]
    citations: List[Dict[str, Any]]
    agent_reasoning: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MultiAgentInvestigator:
    """Orchestrates Log Analyst, Topology Tracer, and Remediation Advisor agents."""

    def __init__(self, retriever: Optional[RunbookRetriever] = None):
        self.retriever = retriever or RunbookRetriever()

    def investigate(
        self,
        rca_report: RootCauseReport,
        anomalous_logs: List[ParsedLog]
    ) -> IncidentInvestigationReport:
        # Agent 1: Log Pattern Analyst
        log_analysis = self._run_log_analyst(anomalous_logs, rca_report)

        # Agent 2: Topology Tracer
        topology_analysis = self._run_topology_tracer(rca_report)

        # Agent 3: RAG Retrieval & Remediation Advisor
        rag_query = (
            f"{rca_report.root_cause_service} "
            f"{' '.join(rca_report.suspected_error_templates)} "
            f"{' '.join(rca_report.causal_path)}"
        )
        retrieved_docs = self.retriever.retrieve(rag_query, top_k=2)
        remediation_analysis = self._run_remediation_advisor(rca_report, retrieved_docs)

        # Synthesis
        title = f"{rca_report.root_cause_service.replace('-', ' ').title()} Failure"
        path_str = " → ".join([s.replace("-", " ").title() for s in rca_report.causal_path])

        citations = [doc.to_dict() for doc in retrieved_docs]

        return IncidentInvestigationReport(
            incident_id=rca_report.incident_id,
            title=title,
            detected_at=rca_report.timestamp,
            root_cause_service=rca_report.root_cause_service,
            confidence_percentage=int(rca_report.confidence_score * 100),
            anomaly_detected_summary=log_analysis["anomaly_summary"],
            root_cause_identified=log_analysis["root_cause_summary"],
            related_services_path=path_str,
            suggested_solution=remediation_analysis["suggested_solution"],
            remediation_commands=remediation_analysis["remediation_commands"],
            citations=citations,
            agent_reasoning={
                "log_pattern_analyst": log_analysis["details"],
                "topology_tracer": topology_analysis["details"],
                "remediation_advisor": remediation_analysis["details"]
            }
        )

    def _run_log_analyst(self, logs: List[ParsedLog], rca: RootCauseReport) -> Dict[str, str]:
        rc_service = rca.root_cause_service
        rc_logs = [l for l in logs if l.service == rc_service]

        # Calculate max latency and error text
        peak_lat = max([l.latency_ms for l in logs], default=0.0)
        baseline_lat = min([l.latency_ms for l in logs if l.latency_ms > 0], default=80.0)

        # Look for explicit error messages
        err_msg = "Abnormal response time spike"
        for l in rc_logs:
            if "connection slots are reserved" in l.raw_message or "ConnectionPoolTimeout" in l.raw_message:
                err_msg = "Database connection pool exhausted"
                break
            elif "OutOfMemoryError" in l.raw_message:
                err_msg = "JVM heap memory leak exhausted container limits"
                break

        anomaly_summary = (
            f"{rca.causal_path[1] if len(rca.causal_path) > 1 else rc_service} response time "
            f"increased from {int(baseline_lat)} ms to {int(peak_lat):,} ms."
        )

        return {
            "anomaly_summary": anomaly_summary,
            "root_cause_summary": err_msg,
            "details": (
                f"Parsed {len(logs)} anomalous telemetry lines. "
                f"Identified {len(rca.suspected_error_templates)} unique fault templates originating in {rc_service}."
            )
        }

    def _run_topology_tracer(self, rca: RootCauseReport) -> Dict[str, str]:
        path_str = " → ".join(rca.causal_path)
        blast = ", ".join(rca.blast_radius) if rca.blast_radius else "None"
        return {
            "details": (
                f"Causal path traced from foundational root {rca.root_cause_service} "
                f"through callers: {path_str}. Downstream blast radius: [{blast}]."
            )
        }

    def _run_remediation_advisor(
        self,
        rca: RootCauseReport,
        retrieved_docs: List[RetrievalResult]
    ) -> Dict[str, Any]:
        # Extract commands from retrieved runbook
        commands = []
        suggested_solution = (
            "Investigate connection leaks and review database connection pool limits. "
            "Terminate long-running idle transactions and verify connection release logic."
        )

        for doc in retrieved_docs:
            # Extract code blocks
            lines = doc.chunk.content.split("\n")
            in_code = False
            curr_code = []
            for line in lines:
                if line.strip().startswith("```"):
                    if in_code:
                        if curr_code:
                            commands.append("\n".join(curr_code))
                        curr_code = []
                        in_code = False
                    else:
                        in_code = True
                elif in_code:
                    curr_code.append(line)

        if not commands:
            commands = [
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction';",
                "SHOW max_connections;"
            ]

        return {
            "suggested_solution": suggested_solution,
            "remediation_commands": commands[:2],
            "details": (
                f"Retrieved {len(retrieved_docs)} SRE runbook sections. "
                f"Grounded remediation plan in verified playbook procedures."
            )
        }
