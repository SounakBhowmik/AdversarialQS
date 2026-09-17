"""Mixed-state kernels; exact states are an oracle upper bound on information access."""

import numpy as np

from ..metrics import uhlmann_fidelity


def state_kernel(left: np.ndarray, right: np.ndarray, kind: str = "hilbert_schmidt") -> np.ndarray:
    """Average matching-setting overlaps; inputs have shape (samples, settings, 2, 2)."""
    if left.ndim != 4 or right.ndim != 4 or left.shape[1:] != right.shape[1:]:
        raise ValueError("Kernels require matching (samples, settings, 2, 2) arrays")
    if kind == "hilbert_schmidt":
        result = np.einsum("nsij,msji->nm", left, right).real / left.shape[1]
    elif kind == "squared_fidelity":
        result = np.array(
            [[np.mean([uhlmann_fidelity(a, b) for a, b in zip(x, y)]) for y in right] for x in left]
        )
    else:
        raise ValueError("Unknown state kernel")
    if not np.isfinite(result).all():
        raise ValueError("Nonfinite kernel")
    return result


def check_gram(matrix: np.ndarray) -> dict:
    """Reject nonfinite/asymmetric matrices; record the minimum eigenvalue and PSD status."""
    if not np.isfinite(matrix).all() or not np.allclose(matrix, matrix.T, atol=1e-10):
        raise ValueError("Gram matrix must be finite and symmetric")
    minimum = float(np.linalg.eigvalsh(matrix)[0])
    return {"minimum_eigenvalue": minimum, "psd_within_1e-10": minimum >= -1e-10}


class StateKernelRegressor:
    """Tomography or ORACLE upper-bound KRR; no claim of superior predictive accuracy.

    If a kernel is indefinite, increase diagonal regularization sufficiently to
    make the training solve positive definite; preserve the original cross-kernel.
    """

    def __init__(
        self, kind: str = "hilbert_schmidt", alpha: float = 0.01, oracle: bool = False
    ) -> None:
        self.kind, self.alpha, self.oracle = kind, alpha, oracle
        self.label = "oracle_upper_bound" if oracle else "tomography_krr"
        if not np.isfinite(alpha) or alpha <= 0:
            raise ValueError("Kernel regularization must be positive")

    def fit(self, states: np.ndarray, fields_microtesla: np.ndarray) -> "StateKernelRegressor":
        """Fit on separately generated clean labeled training data."""
        self.training_states = states.copy()
        gram = state_kernel(states, states, self.kind)
        self.diagnostics = check_gram(gram)
        correction = max(0.0, -self.diagnostics["minimum_eigenvalue"])
        self.diagnostics.update(
            {"eigenvalue_shift": correction, "ridge_alpha": self.alpha, "kernel": self.kind}
        )
        self.mean = float(np.mean(fields_microtesla))
        self.weights = np.linalg.solve(
            gram + (self.alpha + correction) * np.eye(len(gram)), fields_microtesla - self.mean
        )
        return self

    def predict(self, states: np.ndarray) -> np.ndarray:
        """Predict microtesla using matching-setting state features."""
        return state_kernel(states, self.training_states, self.kind) @ self.weights + self.mean
