"""Held-out sequence consistency; no simulator ground-truth input."""

import numpy as np
from scipy.stats import binom

from ..estimators.maximum_likelihood import MaximumLikelihood
from ..measurement.sampling import Observation
from ..physics.ramsey import probability_zero


def verify(observations: list[Observation], estimator: MaximumLikelihood) -> dict:
    """Fit estimation counts and score disjoint verification counts at that estimate."""
    training = [o for o in observations if o.subset == "estimation"]
    heldout = [o for o in observations if o.subset == "verification"]
    if not training or not heldout:
        raise ValueError("Verifier requires both disjoint subsets")
    if {o.command.challenge_id for o in training} & {o.command.challenge_id for o in heldout}:
        raise ValueError("Estimation and verification IDs overlap")
    estimate = estimator.predict(training)
    p = np.clip(
        np.array(
            [
                probability_zero(
                    estimate.field_tesla,
                    o.command.sensing_duration_seconds,
                    o.command.analysis_phase_radians - o.command.preparation_phase_radians,
                    estimator.sensor,
                    o.command.microwave_detuning_rad_per_second,
                )
                for o in heldout
            ]
        ),
        1e-12,
        1 - 1e-12,
    )
    zeros, shots = np.array([o.zeros for o in heldout]), np.array([o.shots for o in heldout])
    return {
        "field_tesla": estimate.field_tesla,
        "confidence_intervals_tesla": estimate.confidence_intervals_tesla,
        "nll": float(-binom.logpmf(zeros, shots, p).sum()),
        "standardized_residual": float(np.mean((zeros - shots * p) ** 2 / (shots * p * (1 - p)))),
    }
