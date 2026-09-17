"""Attacks emit relative control changes; hidden commands never reach attack code."""

from dataclasses import asdict, dataclass, replace

import numpy as np

from ..config import AttackSpec
from ..constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA
from ..control.commands import ControlCommand
from ..defense.challenge import Challenge


@dataclass(frozen=True)
class AttackerView:
    """Entire attack input: slot ID, profile, and explicitly disclosed challenge values."""

    profile: str
    challenge_id: str
    sensing_duration_seconds: float | None
    analysis_phase_radians: float | None
    commitment_time_seconds: float
    challenge_disclosure_time_seconds: float | None
    information: str


@dataclass(frozen=True)
class ControlDelta:
    """Relative pulse/timing alterations applied by the trusted execution boundary."""

    pulse: str = "analysis"
    phase_radians: float = 0.0
    angle_scale: float = 1.0
    i_gain: float = 1.0
    q_gain: float = 1.0
    absolute_seconds: float = 0.0
    relative_timing_error: float = 0.0
    detuning_rad_per_second: float = 0.0
    pulse_detuning_rad_per_second: float = 0.0
    global_delay_seconds: float = 0.0


def attacker_view(spec: AttackSpec, challenge: Challenge) -> AttackerView:
    """Enforce challenge disclosure relative to t=0 release and an actuation deadline.

    A1 knows the nominal schedule, not random replacements. A2 falls back to that
    schedule if disclosure arrives too late. A3 sees the current challenge.
    """
    c = challenge.command
    known = spec.profile == "A3" or (
        spec.profile == "A2" and spec.latency_seconds <= challenge.actuation_window_seconds
    )
    if spec.profile == "A1" and not challenge.randomized:
        known = True
    if known:
        disclosure = (
            spec.latency_seconds
            if spec.profile == "A2"
            else (0.0 if spec.profile == "A3" else -1e-6)
        )
        return AttackerView(
            spec.profile,
            c.challenge_id,
            c.sensing_duration_seconds,
            c.analysis_phase_radians,
            disclosure,
            disclosure,
            "current challenge" if challenge.randomized else "fixed schedule",
        )
    nominal = None if spec.profile == "A0" else challenge.nominal_time_seconds
    disclosure = spec.latency_seconds if spec.profile == "A2" else None
    return AttackerView(
        spec.profile,
        c.challenge_id,
        nominal,
        None,
        -1e-6,
        disclosure,
        "no schedule" if nominal is None else "nominal schedule only; current challenge withheld",
    )


def perturbation(spec: AttackSpec, view: AttackerView) -> ControlDelta:
    """Compute an attack without accessing true field, states, or hidden controls."""
    if spec.profile != view.profile:
        raise ValueError("Attack profile does not match restricted view")
    if spec.kind in {"none", "composite"}:
        return ControlDelta()
    if spec.kind == "phase":
        return ControlDelta(pulse=spec.pulse, phase_radians=spec.phase_radians)
    if spec.kind == "spoof":
        time = (
            view.sensing_duration_seconds
            if view.sensing_duration_seconds is not None
            else spec.reference_time_seconds
        )
        # cos(gamma*B*t + prep - alpha): analysis and preparation have opposite signs.
        sign = -1 if spec.pulse == "analysis" else 1
        return ControlDelta(
            pulse=spec.pulse, phase_radians=sign * GAMMA * spec.target_displacement_tesla * time
        )
    if spec.kind == "timing":
        return ControlDelta(
            absolute_seconds=spec.absolute_seconds, relative_timing_error=spec.relative_timing_error
        )
    if spec.kind == "delay":
        return ControlDelta(global_delay_seconds=spec.absolute_seconds)
    if spec.kind == "frequency":
        return ControlDelta(
            detuning_rad_per_second=spec.detuning_rad_per_second
            or GAMMA * spec.target_displacement_tesla
        )
    return ControlDelta(
        pulse=spec.pulse,
        phase_radians=spec.phase_radians,
        angle_scale=spec.angle_scale,
        i_gain=spec.i_gain,
        q_gain=spec.q_gain,
        pulse_detuning_rad_per_second=spec.detuning_rad_per_second,
    )


def apply_delta(command: ControlCommand, delta: ControlDelta) -> ControlCommand:
    """Apply additive phase, Cartesian I/Q gains, angle scale, then timing/detuning.

    Gains act on actual drive X/Y axes. The attack chooses the transformation,
    while this executor resolves the protected command through the analog path.
    """
    prefix = delta.pulse
    phase = getattr(command, f"{prefix}_phase_radians") + delta.phase_radians
    axis = phase + (np.pi / 2 if prefix == "preparation" else -np.pi / 2)
    x, y = delta.i_gain * np.cos(axis), delta.q_gain * np.sin(axis)
    gain = float(np.hypot(x, y))
    actual_phase = (
        float(np.arctan2(y, x) - (np.pi / 2 if prefix == "preparation" else -np.pi / 2))
        if gain
        else phase
    )
    # Preserve the exact register value under identity gains, including 2*pi wraps.
    if delta.i_gain == delta.q_gain == 1:
        actual_phase = phase
        gain = 1.0
    return replace(
        command,
        **{
            f"{prefix}_phase_radians": actual_phase,
            f"{prefix}_angle_radians": getattr(command, f"{prefix}_angle_radians")
            * delta.angle_scale,
            f"{prefix}_amplitude": getattr(command, f"{prefix}_amplitude") * gain,
            f"{prefix}_detuning_rad_per_second": getattr(
                command, f"{prefix}_detuning_rad_per_second"
            )
            + delta.pulse_detuning_rad_per_second,
            "sensing_duration_seconds": command.sensing_duration_seconds
            * (1 + delta.relative_timing_error)
            + delta.absolute_seconds,
            "microwave_detuning_rad_per_second": command.microwave_detuning_rad_per_second
            + delta.detuning_rad_per_second,
            "global_delay_seconds": command.global_delay_seconds + delta.global_delay_seconds,
        },
    )


def execute(spec: AttackSpec, challenge: Challenge) -> tuple[ControlCommand, list[dict]]:
    """Invoke attacks in listed order and record each capability and control boundary."""
    command = challenge.command
    records = []
    components = spec.components if spec.kind == "composite" else (spec,)
    for component in components:
        if component.kind == "composite":
            nested, logs = execute(component, replace(challenge, command=command))
            command = nested
            records.extend(logs)
            continue
        view = attacker_view(component, challenge)
        attacked = apply_delta(command, perturbation(component, view))
        records.append(
            {
                "attacker_view": asdict(view),
                "parameters": asdict(component),
                "original_command": asdict(command),
                "attacked_command": asdict(attacked),
            }
        )
        command = attacked
    return command, records
