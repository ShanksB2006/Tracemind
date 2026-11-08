"""Abstract Base Class for TraceMind Anomaly Detection Models."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import numpy as np


class BaseAnomalyDetector(ABC):
    """Unified interface for anomaly detection models in TraceMind."""

    @abstractmethod
    def fit(self, X: np.ndarray) -> "BaseAnomalyDetector":
        """Trains the detector on nominal baseline feature vectors."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Returns binary predictions: 0 for nominal, 1 for anomalous."""
        pass

    @abstractmethod
    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """Returns continuous anomaly score in range [0.0, 1.0]."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the model architecture."""
        pass
