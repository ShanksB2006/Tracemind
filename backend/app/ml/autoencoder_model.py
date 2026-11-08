"""Model B: Deep Bottleneck Autoencoder Anomaly Detector.

Learns normal telemetry manifolds and detects incidents via reconstruction error (MSE).
Includes feature-level error attribution for explainable anomaly detection.
"""
from __future__ import annotations
import numpy as np
from sklearn.preprocessing import StandardScaler
from .base import BaseAnomalyDetector


class BottleneckAutoencoder(BaseAnomalyDetector):
    """
    Multi-layer feedforward Autoencoder implemented in NumPy.
    Architecture: Input (D) -> Hidden (H) -> Bottleneck (B) -> Hidden (H) -> Output (D)
    """

    def __init__(
        self,
        bottleneck_dim: int = 4,
        hidden_dim: int = 12,
        lr: float = 0.01,
        epochs: int = 150,
        threshold_sigma: float = 2.5,
        random_state: int = 42
    ):
        self.bottleneck_dim = bottleneck_dim
        self.hidden_dim = hidden_dim
        self.lr = lr
        self.epochs = epochs
        self.threshold_sigma = threshold_sigma
        self.random_state = random_state

        self.scaler = StandardScaler()
        self.weights: dict[str, np.ndarray] = {}
        self.threshold: float = 0.0
        self.mean_train_error: float = 0.0
        self.std_train_error: float = 0.0
        self._is_fitted = False

    @property
    def name(self) -> str:
        return "Bottleneck Autoencoder (Reconstruction MSE)"

    def _init_weights(self, input_dim: int):
        np.random.seed(self.random_state)
        h = max(self.hidden_dim, self.bottleneck_dim * 2)
        b = max(2, min(self.bottleneck_dim, input_dim // 2))

        # Xavier initialization
        def xavier(n_in: int, n_out: int):
            limit = np.sqrt(6.0 / (n_in + n_out))
            return np.random.uniform(-limit, limit, (n_in, n_out))

        self.weights = {
            "W1": xavier(input_dim, h),
            "b1": np.zeros((1, h)),
            "W2": xavier(h, b),
            "b2": np.zeros((1, b)),
            "W3": xavier(b, h),
            "b3": np.zeros((1, h)),
            "W4": xavier(h, input_dim),
            "b4": np.zeros((1, input_dim)),
        }

    def _relu(self, z: np.ndarray) -> np.ndarray:
        return np.maximum(0.0, z)

    def _relu_grad(self, z: np.ndarray) -> np.ndarray:
        return (z > 0.0).astype(np.float32)

    def _forward(self, X: np.ndarray) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        # Encoder
        z1 = np.dot(X, self.weights["W1"]) + self.weights["b1"]
        a1 = self._relu(z1)
        z2 = np.dot(a1, self.weights["W2"]) + self.weights["b2"]
        bottleneck = z2  # Linear bottleneck

        # Decoder
        z3 = np.dot(bottleneck, self.weights["W3"]) + self.weights["b3"]
        a3 = self._relu(z3)
        z4 = np.dot(a3, self.weights["W4"]) + self.weights["b4"]
        reconstruction = z4

        cache = {"X": X, "z1": z1, "a1": a1, "z2": z2, "bottleneck": bottleneck, "z3": z3, "a3": a3}
        return reconstruction, cache

    def fit(self, X: np.ndarray) -> "BottleneckAutoencoder":
        X = np.asarray(X, dtype=np.float32)
        X_scaled = self.scaler.fit_transform(X)
        n_samples, input_dim = X_scaled.shape

        self._init_weights(input_dim)

        # Mini-batch gradient descent with momentum
        velocities = {k: np.zeros_like(v) for k, v in self.weights.items()}
        momentum = 0.9
        batch_size = min(32, n_samples)

        for _ in range(self.epochs):
            indices = np.random.permutation(n_samples)
            X_shuffled = X_scaled[indices]

            for i in range(0, n_samples, batch_size):
                xb = X_shuffled[i:i + batch_size]
                m = xb.shape[0]

                # Forward pass
                recon, cache = self._forward(xb)

                # Loss: MSE
                diff = recon - xb
                grad_z4 = (2.0 / m) * diff
                grad_W4 = np.dot(cache["a3"].T, grad_z4)
                grad_b4 = np.sum(grad_z4, axis=0, keepdims=True)

                grad_a3 = np.dot(grad_z4, self.weights["W4"].T)
                grad_z3 = grad_a3 * self._relu_grad(cache["z3"])
                grad_W3 = np.dot(cache["bottleneck"].T, grad_z3)
                grad_b3 = np.sum(grad_z3, axis=0, keepdims=True)

                grad_bneck = np.dot(grad_z3, self.weights["W3"].T)
                grad_z2 = grad_bneck
                grad_W2 = np.dot(cache["a1"].T, grad_z2)
                grad_b2 = np.sum(grad_z2, axis=0, keepdims=True)

                grad_a1 = np.dot(grad_z2, self.weights["W2"].T)
                grad_z1 = grad_a1 * self._relu_grad(cache["z1"])
                grad_W1 = np.dot(xb.T, grad_z1)
                grad_b1 = np.sum(grad_z1, axis=0, keepdims=True)

                grads = {
                    "W1": grad_W1, "b1": grad_b1,
                    "W2": grad_W2, "b2": grad_b2,
                    "W3": grad_W3, "b3": grad_b3,
                    "W4": grad_W4, "b4": grad_b4,
                }

                # Update weights with momentum
                for k in self.weights:
                    velocities[k] = momentum * velocities[k] - self.lr * grads[k]
                    self.weights[k] += velocities[k]

        # Calibrate reconstruction threshold on training data
        recon_train, _ = self._forward(X_scaled)
        train_errors = np.mean((X_scaled - recon_train) ** 2, axis=1)
        self.mean_train_error = float(np.mean(train_errors))
        self.std_train_error = float(np.std(train_errors))
        self.threshold = self.mean_train_error + self.threshold_sigma * max(1e-5, self.std_train_error)
        self._is_fitted = True
        return self

    def _compute_reconstruction_error(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        X = np.asarray(X, dtype=np.float32)
        X_scaled = self.scaler.transform(X)
        recon, _ = self._forward(X_scaled)
        per_feature_errors = (X_scaled - recon) ** 2
        sample_errors = np.mean(per_feature_errors, axis=1)
        return sample_errors, per_feature_errors

    def predict(self, X: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted yet.")
        errors, _ = self._compute_reconstruction_error(X)
        return (errors > self.threshold).astype(int)

    def score_samples(self, X: np.ndarray) -> np.ndarray:
        """Normalized anomaly score in [0.0, 1.0] based on reconstruction error."""
        if not self._is_fitted:
            raise RuntimeError("Model is not fitted yet.")
        errors, _ = self._compute_reconstruction_error(X)
        # Sigmoid transition centered at threshold
        normalized = 1.0 / (1.0 + np.exp(-3.0 * (errors - self.threshold) / max(1e-4, self.std_train_error)))
        return np.clip(normalized, 0.0, 1.0)

    def get_feature_attributions(self, X: np.ndarray) -> np.ndarray:
        """Returns per-feature contribution to the reconstruction error for explainability."""
        _, per_feature_errors = self._compute_reconstruction_error(X)
        return per_feature_errors
