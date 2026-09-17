"""Bounded field inference with a global phase-alias search."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import chi2

from ..config import SensorConfig
from ..constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA
from ..measurement.sampling import Observation
from ..physics.ramsey import probability_zero


@dataclass(frozen=True)
class Estimate:
    """Point estimate and potentially disconnected profile-likelihood confidence set."""

    field_tesla: float
    confidence_intervals_tesla: tuple[tuple[float, float], ...]


class MaximumLikelihood:
    """Fit only observations and public calibration within declared field bounds."""

    def __init__(self, sensor: SensorConfig, bounds_tesla: tuple[float, float]) -> None:
        self.sensor = sensor
        self.bounds = bounds_tesla
        if not np.isfinite(bounds_tesla).all() or bounds_tesla[0] >= bounds_tesla[1]:
            raise ValueError("Invalid estimator field bounds")

    def nll(self, fields_tesla: np.ndarray, observations: list[Observation]) -> np.ndarray:
        """Binomial NLL without combinatorial constants, one value per candidate field."""
        t = np.array([o.command.sensing_duration_seconds for o in observations])
        alpha = np.array(
            [
                o.command.analysis_phase_radians - o.command.preparation_phase_radians
                for o in observations
            ]
        )
        detuning = np.array([o.command.microwave_detuning_rad_per_second for o in observations])
        p = np.clip(
            probability_zero(np.atleast_1d(fields_tesla)[:, None], t, alpha, self.sensor, detuning),
            1e-12,
            1 - 1e-12,
        )
        zeros = np.array([o.zeros for o in observations])
        shots = np.array([o.shots for o in observations])
        return -(zeros * np.log(p) + (shots - zeros) * np.log1p(-p)).sum(axis=1)

    def predict(self, observations: list[Observation]) -> Estimate:
        """Search aliases globally, refine the minimum, and retain all 95% CI islands."""
        if not observations:
            raise ValueError("MLE needs at least one observation")
        for o in observations:
            c = o.command
            if c.preparation_detuning_rad_per_second or c.analysis_detuning_rad_per_second:
                raise ValueError("Analytical MLE requires resonant intended pulses")
            if not np.isclose(
                c.preparation_angle_radians * c.preparation_amplitude, np.pi / 2
            ) or not np.isclose(c.analysis_angle_radians * c.analysis_amplitude, np.pi / 2):
                raise ValueError("Analytical MLE requires intended ideal pi/2 pulses")
        span = self.bounds[1] - self.bounds[0]
        cycles = (
            GAMMA
            * span
            * max(o.command.sensing_duration_seconds for o in observations)
            / (2 * np.pi)
        )
        grid = np.linspace(*self.bounds, max(2049, int(128 * cycles) + 1))
        loss = self.nll(grid, observations)
        best = int(np.argmin(loss))
        lo, hi = grid[max(0, best - 1)], grid[min(len(grid) - 1, best + 1)]
        # Optimize in microtesla to avoid scipy's absolute-tolerance floor in SI units.
        fit = minimize_scalar(
            lambda x: self.nll(np.array([x * 1e-6]), observations)[0],
            bounds=(lo * 1e6, hi * 1e6),
            method="bounded",
            options={"xatol": 1e-10},
        )
        candidates = np.array([self.bounds[0], fit.x * 1e-6, self.bounds[1]])
        candidate_loss = self.nll(candidates, observations)
        field = float(candidates[np.argmin(candidate_loss)])
        accepted = loss <= candidate_loss.min() + chi2.ppf(0.95, 1) / 2
        # Conservative half-cell expansion avoids understating finite-grid intervals.
        indices = np.flatnonzero(accepted)
        groups = np.split(indices, np.flatnonzero(np.diff(indices) > 1) + 1)
        step = grid[1] - grid[0]
        intervals = tuple(
            (
                float(max(self.bounds[0], grid[g[0]] - step / 2)),
                float(min(self.bounds[1], grid[g[-1]] + step / 2)),
            )
            for g in groups
            if len(g)
        )
        return Estimate(field, intervals)
