"""Optional QuTiP rectangular-pulse diagnostic backend; instantaneous model is default."""

from dataclasses import replace

import numpy as np

from ..config import SensorConfig
from ..constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA
from ..control.commands import ControlCommand, resolve
from .density_matrix import StateTrace, paulis
from .ramsey import coherence


def simulate_pulses(
    field_tesla: float,
    command: ControlCommand,
    sensor: SensorConfig,
    pulse_duration_seconds: float = 20e-9,
) -> StateTrace:
    """Resolve finite coherent rectangular pulses with QuTiP propagators.

    Includes sensing-field and reference detuning during pulses. Dephasing acts
    only during free evolution; no leakage, shaped envelopes or pulse dissipation.
    """
    try:
        import qutip
    except ImportError as exc:
        raise ImportError('Install the optional backend with pip install -e ".[pulse]"') from exc
    if not np.isfinite(pulse_duration_seconds) or pulse_duration_seconds <= 0:
        raise ValueError("pulse_duration_seconds must be finite and positive")
    if not np.isfinite(field_tesla):
        raise ValueError("field_tesla must be finite")
    op = resolve(replace(command, pulse_duration_seconds=pulse_duration_seconds))
    sigma = [qutip.Qobj(p) for p in paulis()]
    omega = GAMMA * field_tesla + op.detuning_rad_per_second

    def pulse(vector: tuple[float, float, float]) -> np.ndarray:
        h = (
            sum(v / pulse_duration_seconds * s / 2 for v, s in zip(vector, sigma))
            + omega * sigma[2] / 2
        )
        return (-1j * h * pulse_duration_seconds).expm().full()

    initial = np.diag([1.0, 0.0]).astype(complex)
    u = pulse(op.preparation_rotation)
    prepared = u @ initial @ u.conj().T
    free = (-1j * omega * sigma[2] * op.sensing_duration_seconds / 2).expm().full()
    before = free @ prepared @ free.conj().T
    before[0, 1] *= coherence(op.sensing_duration_seconds, sensor)
    before[1, 0] = before[0, 1].conjugate()
    u = pulse(op.analysis_rotation)
    final = u @ before @ u.conj().T
    p = sensor.readout_error + (1 - 2 * sensor.readout_error) * final[0, 0].real
    return StateTrace(initial, prepared, before, final, op, float(np.clip(p, 0, 1)))
