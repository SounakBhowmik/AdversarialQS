"""Fast ideal-pulse Ramsey probability, including dephasing and readout."""

import numpy as np
from numpy.typing import ArrayLike, NDArray

from ..config import SensorConfig
from ..constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA


def coherence(time_seconds: ArrayLike, sensor: SensorConfig) -> NDArray:
    """Return exp[-(t/T2*)**p] for nonnegative sensing separations."""
    t = np.asarray(time_seconds)
    if np.any(t < 0) or not np.isfinite(t).all():
        raise ValueError("time_seconds must be finite and nonnegative")
    return np.exp(-((t / sensor.t2_star_seconds) ** sensor.dephasing_exponent))


def probability_zero(
    field_tesla: ArrayLike,
    time_seconds: ArrayLike,
    phase_radians: ArrayLike,
    sensor: SensorConfig,
    detuning_rad_per_second: float = 0.0,
) -> NDArray:
    """P(recorded 0) = [1 + (1-2 eta) C(t) cos(gamma B t - alpha)]/2."""
    phase = (GAMMA * np.asarray(field_tesla) + detuning_rad_per_second) * np.asarray(
        time_seconds
    ) - np.asarray(phase_radians)
    return (
        1 + (1 - 2 * sensor.readout_error) * coherence(time_seconds, sensor) * np.cos(phase)
    ) / 2
