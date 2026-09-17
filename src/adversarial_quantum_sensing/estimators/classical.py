"""Standard learning baselines with training-only scaling and microtesla targets."""

import numpy as np
from sklearn.kernel_ridge import KernelRidge
from sklearn.linear_model import Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..measurement.sampling import Observation


def features(observations: list[Observation]) -> np.ndarray:
    """Use counts and protected challenge values, never simulator field or attack labels."""
    return np.array(
        [
            [
                2 * o.zeros / o.shots - 1,
                o.command.sensing_duration_seconds * 1e6,
                np.sin(o.command.analysis_phase_radians),
                np.cos(o.command.analysis_phase_radians),
            ]
            for o in observations
        ]
    ).ravel()


def learning_estimators(seed: int) -> dict:
    """Return linear, RBF KRR and MLP regressors; target units are microtesla."""
    return {
        "linear": make_pipeline(StandardScaler(), Ridge(alpha=1e-3)),
        "rbf_krr": make_pipeline(
            StandardScaler(), KernelRidge(alpha=0.01, kernel="rbf", gamma=0.03)
        ),
        "mlp": make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(32,),
                solver="lbfgs",
                alpha=0.1,
                max_iter=1000,
                random_state=seed,
            ),
        ),
    }
