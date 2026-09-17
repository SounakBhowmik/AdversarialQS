"""State, distribution, regression and detector metrics with explicit conventions."""

import numpy as np
from scipy.special import xlogy
from scipy.stats import binom
from sklearn.metrics import roc_auc_score, roc_curve


def uhlmann_fidelity(rho: np.ndarray, sigma: np.ndarray) -> float:
    """Squared Uhlmann fidelity F=(Tr sqrt(sqrt(rho) sigma sqrt(rho)))**2.

    For normalized 2x2 density matrices, F=Tr(rho sigma)+2 sqrt(det rho det sigma).
    The closed qubit expression is stable at pure states and is never squared again.
    """
    overlap = np.trace(rho @ sigma).real
    determinants = max(0.0, float(np.linalg.det(rho).real)) * max(
        0.0, float(np.linalg.det(sigma).real)
    )
    return float(np.clip(overlap + 2 * np.sqrt(determinants), 0, 1))


def trace_distance(rho: np.ndarray, sigma: np.ndarray) -> float:
    """Return one half the trace norm of rho-sigma for Hermitian states."""
    return float(np.abs(np.linalg.eigvalsh(rho - sigma)).sum() / 2)


def bernoulli_kl(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """KL(Bernoulli(p)||Bernoulli(q)), in nats, with exact zero conventions."""
    p, q = np.asarray(p), np.asarray(q)
    return xlogy(p, p) - xlogy(p, q) + xlogy(1 - p, 1 - p) - xlogy(1 - p, 1 - q)


def log_likelihood_ratio(
    zeros: np.ndarray, shots: np.ndarray, attacked: np.ndarray, clean: np.ndarray
) -> float:
    """Exact binomial log L(attacked)/L(clean), including boundary probabilities."""
    return float(np.sum(binom.logpmf(zeros, shots, attacked) - binom.logpmf(zeros, shots, clean)))


def regression_metrics(truth: np.ndarray, predicted: np.ndarray) -> dict:
    """RMSE, MAE and signed bias, all in tesla."""
    errors = np.asarray(predicted) - np.asarray(truth)
    return {
        "rmse_tesla": float(np.sqrt(np.mean(errors**2))),
        "mae_tesla": float(np.mean(np.abs(errors))),
        "bias_tesla": float(np.mean(errors)),
    }


def detection_metrics(
    clean: np.ndarray, attacked: np.ndarray, calibration: np.ndarray
) -> tuple[dict, dict]:
    """Calibrate thresholds independently; evaluate held-out FPR, TPR and ROC."""
    labels = np.r_[np.zeros(len(clean)), np.ones(len(attacked))]
    scores = np.r_[clean, attacked]
    fpr, tpr, _ = roc_curve(labels, scores)
    metrics = {"roc_auc": float(roc_auc_score(labels, scores))}
    for rate in (0.01, 0.05):
        threshold = float(np.quantile(calibration, 1 - rate, method="higher"))
        suffix = f"{int(rate * 100)}pct"
        metrics.update(
            {
                f"threshold_{suffix}": threshold,
                f"tpr_at_calibrated_{suffix}": float(np.mean(attacked > threshold)),
                f"heldout_fpr_at_calibrated_{suffix}": float(np.mean(clean > threshold)),
            }
        )
    return metrics, {"fpr": fpr.tolist(), "tpr": tpr.tolist()}
