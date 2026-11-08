"""Model A: Unsupervised Isolation Forest Anomaly Detector.

Uses tree-based spatial partitioning on windowed metric and event frequency vectors.
"""
from __future__ import annotations
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from .base import BaseAnomalyDetector


class IsolationForestDetector(BaseAnomalyDetector):
    """Isolation Forest implementation for multi-service telemetry anomaly detection."""

    def __init__(self, n_estimators: int = 100, contamination: float = 0.05, random_state: int = 42):
        self.n_estimators = n_estimators
        self.contamination = contamination
        self.random_state = random_state
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state
        )
        self.scaler = StandardScaler()
        self._is_fitted = False

    @property
    def name(self) -> str:
        return "Isolation Forest (Tree Partitioning)"

    def fit(self, X: np.ndarray) -> "IsolationForestDetector":
        """Fits scaler and Isolation Forest on baseline nominal feature vectors."""
        X = np.asarray(X, dtype=np.float32)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled)
        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns binary predictions: 0 for nominal, 1 for anomaly."""
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted yet. Call fit() first.")
        X = np.asarray(X, dtype=np.float32)
        X_scaled = self.scaler.transform(X)
        # Isolation Forest returns -1 for anomaly, 1 for inlier
        raw_preds = self.model.predict(X_scaled)
        return (raw_preds == -1).astype(int)

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """
        Returns normalized anomaly score between [0.0, 1.0].
        Scores > 0.5 represent anomalous behavior.
        """
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted yet. Call fit() first.")
        X = np.asarray(X, dtype=np.float32)
        X_scaled = self.scaler.transform(X)
        # score_samples returns opposite of anomaly score (lower is more anomalous)
        raw_scores = self.model.score_samples(X_scaled)
        # Invert and normalize using sigmoid-like scaling
        # Offset is model.offset_
        anomaly_scores = -raw_scores
        # Normalize to [0, 1] range relative to threshold
        threshold = -self.model.offset_
        # Calibrated normalized score
        normalized = 1.0 / (1.0 + np.exp(-10.0 * (anomaly_scores - threshold)))
        return np.clip(normalized, 0.0, 1.0)
