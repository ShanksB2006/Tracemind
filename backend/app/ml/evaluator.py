"""Evaluation metrics suite for anomaly detection models."""
from __future__ import annotations
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, List
import numpy as np
from .base import BaseAnomalyDetector


@dataclass
class EvaluationReport:
    model_name: str
    precision: float
    recall: float
    f1_score: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    detection_latency_steps: int
    avg_inference_latency_ms: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnomalyEvaluator:
    """Evaluates anomaly detection performance against ground truth labels."""

    @staticmethod
    def evaluate(
        model: BaseAnomalyDetector,
        X_test: np.ndarray,
        y_true: np.ndarray,
        warmup_runs: int = 5
    ) -> EvaluationReport:
        y_true = np.asarray(y_true, dtype=int)
        n_samples = len(y_true)

        # Warmup runs
        for _ in range(warmup_runs):
            _ = model.predict(X_test[:min(10, n_samples)])

        # Measure inference latency
        start_time = time.perf_counter()
        y_pred = model.predict(X_test)
        total_time_ms = (time.perf_counter() - start_time) * 1000.0
        avg_latency_ms = total_time_ms / max(1, n_samples)

        # Confusion matrix
        tp = int(np.sum((y_pred == 1) & (y_true == 1)))
        fp = int(np.sum((y_pred == 1) & (y_true == 0)))
        fn = int(np.sum((y_pred == 0) & (y_true == 1)))
        tn = int(np.sum((y_pred == 0) & (y_true == 0)))

        precision = tp / max(1, (tp + fp))
        recall = tp / max(1, (tp + fn))
        f1 = (2.0 * precision * recall) / max(1e-6, (precision + recall))

        # Detection Latency (steps between first true anomaly and first positive detection)
        first_true_idx = np.where(y_true == 1)[0]
        first_pred_idx = np.where(y_pred == 1)[0]

        if len(first_true_idx) > 0 and len(first_pred_idx) > 0:
            first_true = first_true_idx[0]
            # Find first detection on or after first true incident
            valid_preds = first_pred_idx[first_pred_idx >= first_true]
            if len(valid_preds) > 0:
                detection_latency = int(valid_preds[0] - first_true)
            else:
                detection_latency = n_samples
        else:
            detection_latency = 0

        return EvaluationReport(
            model_name=model.name,
            precision=round(float(precision), 4),
            recall=round(float(recall), 4),
            f1_score=round(float(f1), 4),
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            detection_latency_steps=detection_latency,
            avg_inference_latency_ms=round(float(avg_latency_ms), 4)
        )
