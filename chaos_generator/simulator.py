"""CLI and programmatic harness for the microservice chaos log simulator."""
from __future__ import annotations
import argparse
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .topology import ServiceTopology
from .scenarios import PaymentDBExhaustionScenario, MemoryLeakScenario


def run_simulation(
    scenario_name: str = "payment_db_exhaustion",
    duration_seconds: int = 60,
    output_path: Optional[str] = None,
    output_json: bool = False,
    sleep_interval: float = 0.05
):
    topology = ServiceTopology()

    if scenario_name == "payment_db_exhaustion":
        scenario = PaymentDBExhaustionScenario(topology)
    elif scenario_name == "memory_leak":
        scenario = MemoryLeakScenario(topology)
    else:
        raise ValueError(f"Unknown scenario: {scenario_name}. Available: payment_db_exhaustion, memory_leak")

    out_file = None
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        out_file = open(output_path, "w", encoding="utf-8")

    total_logs = 0
    print(f"[*] Starting TraceMind Chaos Simulation: [{scenario_name}] for {duration_seconds}s...")

    start_time = datetime.now(timezone.utc)
    try:
        for tick in range(duration_seconds):
            entries = scenario.generate_tick(tick, duration_seconds, base_time=start_time)
            for entry in entries:
                total_logs += 1
                line = entry.to_json() if output_json else entry.to_formatted_line()

                if out_file:
                    out_file.write(line + "\n")
                else:
                    print(line)

            if sleep_interval > 0:
                time.sleep(sleep_interval)

        print(f"[✓] Simulation complete. Generated {total_logs} log entries.")
        if output_path:
            print(f"[✓] Logs saved to: {output_path}")

    finally:
        if out_file:
            out_file.close()


def main():
    parser = argparse.ArgumentParser(description="TraceMind Chaos Microservice Log Generator")
    parser.add_argument(
        "--scenario",
        default="payment_db_exhaustion",
        choices=["payment_db_exhaustion", "memory_leak"],
        help="Failure scenario to simulate"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration of simulation in seconds"
    )
    parser.add_argument(
        "--output",
        default="data/logs/chaos_payment.log",
        help="Output file path (default: data/logs/chaos_payment.log)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON Lines format instead of plain text"
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Simulate in real-time (1s sleep between ticks)"
    )

    args = parser.parse_args()
    sleep = 1.0 if args.realtime else 0.01

    run_simulation(
        scenario_name=args.scenario,
        duration_seconds=args.duration,
        output_path=args.output,
        output_json=args.json,
        sleep_interval=sleep
    )


if __name__ == "__main__":
    main()
