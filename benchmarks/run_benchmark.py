"""Automated Benchmark Suite: Model A (Isolation Forest) vs Model B (Reconstruction Autoencoder).

Generates synthetic microservice telemetry, trains baseline models on nominal logs,
and computes Precision, Recall, F1, Detection Delay, and Inference Latency.
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from chaos_generator.topology import ServiceTopology
from chaos_generator.scenarios import PaymentDBExhaustionScenario
from backend.app.ingestion.parser import LogIngestionEngine, ParsedLog
from backend.app.ingestion.windowing import FeatureWindowExtractor, WindowMetrics
from backend.app.ml.isolation_forest_model import IsolationForestDetector
from backend.app.ml.autoencoder_model import BottleneckAutoencoder
from backend.app.ml.evaluator import AnomalyEvaluator, EvaluationReport


def generate_benchmark_data(num_ticks: int = 120, window_size_sec: float = 2.0):
    """Generates nominal and chaos log streams and extracts feature vectors with ground truth."""
    topology = ServiceTopology()
    scenario = PaymentDBExhaustionScenario(topology)
    engine = LogIngestionEngine()

    start_time = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Train set: Pure nominal baseline (120 seconds of healthy operation)
    nominal_logs: list[ParsedLog] = []
    for tick in range(num_ticks):
        raw_entries = scenario.generate_tick(0, 100, base_time=start_time + timedelta(seconds=tick))
        for e in raw_entries:
            parsed = engine.parse_line(e.to_formatted_line())
            if parsed:
                nominal_logs.append(parsed)

    # 2. Test set: Full chaos lifecycle (Nominal -> Degradation -> Critical Failure -> Recovery)
    test_start_time = start_time + timedelta(seconds=num_ticks + 60)
    test_logs: list[ParsedLog] = []

    for tick in range(num_ticks):
        raw_entries = scenario.generate_tick(tick, num_ticks, base_time=test_start_time + timedelta(seconds=tick))
        for e in raw_entries:
            parsed = engine.parse_line(e.to_formatted_line())
            if parsed:
                test_logs.append(parsed)

    # Extract windows
    extractor = FeatureWindowExtractor(window_size_seconds=window_size_sec)
    train_windows = extractor.extract_windows(nominal_logs)
    test_windows = extractor.extract_windows(test_logs)

    all_event_ids = [c.cluster_id for c in engine.drain.clusters]

    X_train = np.array([w.to_feature_vector(all_event_ids) for w in train_windows], dtype=np.float32)
    X_test = np.array([w.to_feature_vector(all_event_ids) for w in test_windows], dtype=np.float32)

    # Label test windows: chaos is active between 25% and 80% of duration
    n_test_windows = len(test_windows)
    y_test = np.zeros(n_test_windows, dtype=int)
    for i in range(n_test_windows):
        ratio = i / max(1, n_test_windows)
        if 0.25 <= ratio < 0.80:
            y_test[i] = 1

    return X_train, X_test, y_test, len(all_event_ids)


def run_benchmark():
    print("=" * 75)
    print("TraceMind: ML Anomaly Detection Benchmark Execution")
    print("=" * 75)

    print("\n[1/4] Generating synthetic microservice telemetry benchmark dataset...")
    X_train, X_test, y_test, num_features = generate_benchmark_data(num_ticks=120, window_size_sec=2.0)
    print(f"      • Training windows (Nominal baseline): {X_train.shape[0]} samples")
    print(f"      • Testing windows (Mixed lifecycle):    {X_test.shape[0]} samples")
    print(f"      • Feature dimensions per window:       {X_train.shape[1]} metrics & template counts")
    print(f"      • True Anomalous Windows in Test:      {int(np.sum(y_test))} / {len(y_test)}")

    # Model A: Isolation Forest
    print("\n[2/4] Training Model A: Isolation Forest...")
    model_a = IsolationForestDetector(n_estimators=100, contamination=0.08, random_state=42)
    model_a.fit(X_train)
    report_a = AnomalyEvaluator.evaluate(model_a, X_test, y_test)

    # Model B: Bottleneck Autoencoder
    print("\n[3/4] Training Model B: Bottleneck Autoencoder (MSE Reconstruction)...")
    model_b = BottleneckAutoencoder(bottleneck_dim=4, hidden_dim=12, lr=0.01, epochs=100, threshold_sigma=2.0)
    model_b.fit(X_train)
    report_b = AnomalyEvaluator.evaluate(model_b, X_test, y_test)

    # Print results
    print("\n[4/4] Benchmark Results Summary:\n")
    reports = [report_a, report_b]

    header = f"| {'Model Architecture':<42} | {'Precision':<9} | {'Recall':<7} | {'F1-Score':<8} | {'Latency (ms)':<12} | {'Lag (Steps)':<11} |"
    divider = f"|:{'-'*42}-|-{'-'*9}:|-{'-'*7}:|-{'-'*8}:|-{'-'*12}:|-{'-'*11}:|"
    print(header)
    print(divider)

    for r in reports:
        row = (
            f"| {r.model_name:<42} "
            f"| {r.precision:<9.4f} "
            f"| {r.recall:<7.4f} "
            f"| {r.f1_score:<8.4f} "
            f"| {r.avg_inference_latency_ms:<12.4f} "
            f"| {r.detection_latency_steps:<11} |"
        )
        print(row)

    # Save to JSON
    out_dir = PROJECT_ROOT / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "benchmark_results.json"

    data = {
        "dataset": {
            "train_samples": int(X_train.shape[0]),
            "test_samples": int(X_test.shape[0]),
            "feature_count": int(num_features),
            "anomalous_ratio": float(np.mean(y_test))
        },
        "results": [r.to_dict() for r in reports]
    }

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"\n[✓] Benchmark results saved to: {out_file}")


if __name__ == "__main__":
    run_benchmark()
