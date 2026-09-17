"""Two-level density evolution with explicit pulse and measurement boundaries."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..config import SensorConfig
from ..constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA
from ..control.commands import ControlCommand, PhysicalOperation, resolve
from .ramsey import coherence


def paulis() -> NDArray:
    """Return X, Y and Z in the computational basis."""
    return np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]], dtype=complex)


def rotation(vector_radians: tuple[float, float, float]) -> NDArray:
    """Compute exp(-i vector.sigma/2) without a general matrix exponential."""
    vector = np.asarray(vector_radians)
    angle = np.linalg.norm(vector)
    if angle == 0:
        return np.eye(2, dtype=complex)
    return np.cos(angle / 2) * np.eye(2) - 1j * np.sin(angle / 2) * np.einsum(
        "i,ijk->jk", vector / angle, paulis()
    )


@dataclass(frozen=True)
class StateTrace:
    """Ground-truth state record; oracle access must be explicitly requested."""

    initialized: NDArray
    prepared: NDArray
    preanalysis: NDArray
    premeasurement: NDArray
    physical: PhysicalOperation
    probability_zero: float


def simulate(field_tesla: float, command: ControlCommand, sensor: SensorConfig) -> StateTrace:
    """Evolve one NV; a global delay has no effect for a static field."""
    if not np.isfinite(field_tesla):
        raise ValueError("field_tesla must be finite")
    op = resolve(command)
    initialized = np.diag([1.0, 0.0]).astype(complex)
    prep = rotation(op.preparation_rotation)
    prepared = prep @ initialized @ prep.conj().T
    phase = (GAMMA * field_tesla + op.detuning_rad_per_second) * op.sensing_duration_seconds
    free = rotation((0, 0, phase))
    before = free @ prepared @ free.conj().T
    # Pure dephasing leaves populations invariant; readout is NOT a state channel.
    before[0, 1] *= coherence(op.sensing_duration_seconds, sensor)
    before[1, 0] = before[0, 1].conjugate()
    analysis = rotation(op.analysis_rotation)
    final = analysis @ before @ analysis.conj().T
    p = sensor.readout_error + (1 - 2 * sensor.readout_error) * final[0, 0].real
    return StateTrace(initialized, prepared, before, final, op, float(np.clip(p, 0, 1)))
