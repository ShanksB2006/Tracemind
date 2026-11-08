"""Log Stream Ingestion & Parsing Engine.

Extracts telemetry fields from raw log lines and maps messages to Drain event clusters.
"""
from __future__ import annotations
import argparse
import json
import re
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict, Any, Generator
from .drain_miner import DrainParser


@dataclass
class ParsedLog:
    timestamp: str
    service: str
    level: str
    trace_id: str
    span_id: str
    status_code: int
    latency_ms: float
    raw_message: str
    event_id: str
    template: str
    attributes: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LogIngestionEngine:
    """Parses raw text and structured logs into normalized ParsedLog events."""

    # Matches: 2026-11-08 08:18:16.024 [INFO    ] [service-name] [trace=xxx span=yyy] status=200 latency=120.4ms - message
    LINE_REGEX = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
        r"\[(?P<level>[A-Z]+)\s*\]\s+"
        r"\[(?P<service>[a-zA-Z0-9_\-]+)\]\s+"
        r"\[trace=(?P<trace>[a-zA-Z0-9_\-]+)\s+span=(?P<span>[a-zA-Z0-9_\-]+)\]\s+"
        r"status=(?P<status>\d+)\s+latency=(?P<latency>[\d\.]+)ms\s+-\s+"
        r"(?P<message>.*)$"
    )

    def __init__(self):
        self.drain = DrainParser(depth=4, sim_threshold=0.5)

    def parse_line(self, line: str) -> Optional[ParsedLog]:
        line = line.strip()
        if not line:
            return None

        # Check if line is JSON
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                raw_msg = data.get("message", "")
                event_id, template = self.drain.parse(raw_msg)
                return ParsedLog(
                    timestamp=data.get("timestamp", ""),
                    service=data.get("service", "unknown"),
                    level=data.get("level", "INFO"),
                    trace_id=data.get("trace_id", ""),
                    span_id=data.get("span_id", ""),
                    status_code=int(data.get("status_code", 200)),
                    latency_ms=float(data.get("latency_ms", 0.0)),
                    raw_message=raw_msg,
                    event_id=event_id,
                    template=template,
                    attributes=data.get("attributes", {})
                )
            except Exception:
                pass

        # Regex match for standard log format
        match = self.LINE_REGEX.match(line)
        if match:
            raw_msg = match.group("message")
            event_id, template = self.drain.parse(raw_msg)
            return ParsedLog(
                timestamp=match.group("timestamp"),
                service=match.group("service"),
                level=match.group("level").strip(),
                trace_id=match.group("trace"),
                span_id=match.group("span"),
                status_code=int(match.group("status")),
                latency_ms=float(match.group("latency")),
                raw_message=raw_msg,
                event_id=event_id,
                template=template,
                attributes={}
            )

        # Fallback unstructured log parsing
        event_id, template = self.drain.parse(line)
        return ParsedLog(
            timestamp="",
            service="generic",
            level="INFO",
            trace_id="",
            span_id="",
            status_code=200,
            latency_ms=0.0,
            raw_message=line,
            event_id=event_id,
            template=template,
            attributes={}
        )

    def parse_file(self, file_path: str) -> List[ParsedLog]:
        results: List[ParsedLog] = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                parsed = self.parse_line(line)
                if parsed:
                    results.append(parsed)
        return results


def main():
    parser = argparse.ArgumentParser(description="TraceMind Ingestion & Drain Log Parser")
    parser.add_argument("--input", required=True, help="Path to raw log file")
    parser.add_argument("--limit", type=int, default=10, help="Print first N parsed entries")
    args = parser.parse_args()

    engine = LogIngestionEngine()
    print(f"[*] Ingesting and parsing logs from {args.input}...")
    logs = engine.parse_file(args.input)
    print(f"[✓] Parsed {len(logs)} log entries into {len(engine.drain.clusters)} unique event templates.\n")

    print(f"=== Top Event Templates Discovered ===")
    for cluster in engine.drain.clusters[:8]:
        print(f"  [{cluster.cluster_id}] (count={cluster.size}): {cluster.template_str}")

    print(f"\n=== First {args.limit} Parsed Telemetry Entries ===")
    for entry in logs[:args.limit]:
        print(f"  {entry.timestamp} | {entry.service:<15} | {entry.level:<8} | "
              f"lat={entry.latency_ms:>6.1f}ms | Event={entry.event_id} | {entry.raw_message[:50]}...")


if __name__ == "__main__":
    main()
