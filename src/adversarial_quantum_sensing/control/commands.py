"""Control records carry SI units; no simulator ground truth is stored here."""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ControlCommand:
    """One Ramsey setting; preparation phase zero denotes a +Y pi/2 pulse."""

    sensing_duration_seconds: float
    analysis_phase_radians: float = 0.0
    preparation_phase_radians: float = 0.0
    preparation_angle_radians: float = float(np.pi / 2)
    preparation_amplitude: float = 1.0
    analysis_angle_radians: float = float(np.pi / 2)
    analysis_amplitude: float = 1.0
    microwave_detuning_rad_per_second: float = 0.0
    preparation_detuning_rad_per_second: float = 0.0
    analysis_detuning_rad_per_second: float = 0.0
    pulse_duration_seconds: float = 20e-9
    global_delay_seconds: float = 0.0
    challenge_id: str = "0"
    node_id: str = "nv0"

    def __post_init__(self) -> None:
        values = [v for v in self.__dict__.values() if isinstance(v, (float, int))]
        if not np.isfinite(values).all() or self.sensing_duration_seconds < 0:
            raise ValueError("Controls must be finite; pulse separation cannot be negative")
        if min(self.preparation_amplitude, self.analysis_amplitude) < 0:
            raise ValueError("Pulse amplitudes must be nonnegative")
        if self.pulse_duration_seconds <= 0:
            raise ValueError("pulse_duration_seconds must be positive")


@dataclass(frozen=True)
class PhysicalOperation:
    """Resolved rotation vectors, phase accumulation rate offset and separation."""

    preparation_rotation: tuple[float, float, float]
    analysis_rotation: tuple[float, float, float]
    sensing_duration_seconds: float
    detuning_rad_per_second: float
    pulse_duration_seconds: float


def resolve(command: ControlCommand) -> PhysicalOperation:
    """Resolve coherent rotations, integrating pulse-local detuning over pulse duration."""
    prep = command.preparation_phase_radians
    alpha = command.analysis_phase_radians
    a = command.preparation_angle_radians * command.preparation_amplitude
    b = command.analysis_angle_radians * command.analysis_amplitude
    # +Y prepares +X; -Y rotated by alpha analyzes X cos(alpha) + Y sin(alpha).
    return PhysicalOperation(
        (
            -a * np.sin(prep),
            a * np.cos(prep),
            command.preparation_detuning_rad_per_second * command.pulse_duration_seconds,
        ),
        (
            b * np.sin(alpha),
            -b * np.cos(alpha),
            command.analysis_detuning_rad_per_second * command.pulse_duration_seconds,
        ),
        command.sensing_duration_seconds,
        command.microwave_detuning_rad_per_second,
        command.pulse_duration_seconds,
    )
