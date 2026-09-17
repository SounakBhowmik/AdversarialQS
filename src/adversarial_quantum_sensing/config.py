"""Strict SI-valued configuration; simulator fields never enter estimator inputs."""

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import yaml


@dataclass(frozen=True)
class SensorConfig:
    """Public calibration, without a true field or hidden attack parameters."""

    t2_star_seconds: float = 100e-6
    dephasing_exponent: float = 1.0
    readout_error: float = 0.10

    def __post_init__(self) -> None:
        if not np.isfinite(self.t2_star_seconds) or self.t2_star_seconds <= 0:
            raise ValueError("t2_star_seconds must be finite and positive (seconds)")
        if not np.isfinite(self.dephasing_exponent) or self.dephasing_exponent <= 0:
            raise ValueError("dephasing_exponent must be finite and positive")
        if not 0 <= self.readout_error < 0.5:
            raise ValueError("readout_error must be in [0, 0.5)")


@dataclass(frozen=True)
class AttackSpec:
    """Attacker-owned parameters; positive target displacement means B + delta_B."""

    kind: str = "none"
    profile: str = "A1"
    pulse: str = "analysis"
    phase_radians: float = 0.0
    target_displacement_tesla: float = 0.1e-6
    absolute_seconds: float = 0.0
    relative_timing_error: float = 0.0
    angle_scale: float = 1.0
    i_gain: float = 1.0
    q_gain: float = 1.0
    detuning_rad_per_second: float = 0.0
    latency_seconds: float = 0.0
    reference_time_seconds: float = 20e-6
    components: tuple["AttackSpec", ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in {
            "none",
            "phase",
            "spoof",
            "timing",
            "iq",
            "frequency",
            "delay",
            "composite",
        }:
            raise ValueError(f"Unknown attack kind: {self.kind}")
        if self.profile not in {"A0", "A1", "A2", "A3"}:
            raise ValueError("profile must be A0, A1, A2 or A3")
        if self.pulse not in {"preparation", "analysis"}:
            raise ValueError("pulse must be preparation or analysis")
        for key, value in asdict(self).items():
            if isinstance(value, (float, int)) and not np.isfinite(value):
                raise ValueError(f"{key} must be finite")
        if self.latency_seconds < 0 or self.reference_time_seconds <= 0:
            raise ValueError("Latency must be nonnegative; reference time must be positive")
        if self.relative_timing_error <= -1 or min(self.i_gain, self.q_gain, self.angle_scale) < 0:
            raise ValueError("Invalid timing scale or negative I/Q gain")
        if self.kind == "composite" and not self.components:
            raise ValueError("Composite requires ordered components")
        if any(
            c.profile != self.profile or c.latency_seconds != self.latency_seconds
            for c in self.components
        ):
            raise ValueError("Composite components must share the outer profile and latency")


@dataclass(frozen=True)
class ExperimentConfig:
    """Experiment design only; each true field is generated in the runner."""

    seed: int = 20260910
    field_min_tesla: float = 0.0
    field_max_tesla: float = 2e-6
    sensing_times_seconds: tuple[float, ...] = (5e-6, 10e-6, 20e-6, 40e-6, 60e-6)
    analysis_phases_radians: tuple[float, ...] = (0.0, float(np.pi / 2))
    shots_per_setting: int = 1000
    train_samples: int = 128
    test_samples: int = 32
    calibration_samples: int = 128
    random_times: bool = False
    random_phases: bool = False
    time_distribution: str = "uniform"
    phase_distribution: str = "uniform"
    challenge_granularity: str = "setting"
    actuation_window_seconds: float = 2e-6
    target_tolerance_tesla: float = 0.025e-6
    sensor: SensorConfig = field(default_factory=SensorConfig)
    attack: AttackSpec = field(default_factory=AttackSpec)
    phase_sweep_radians: tuple[float, ...] = (0.001, 0.003, 0.01, 0.03, 0.1)
    target_sweep_tesla: tuple[float, ...] = (0.025e-6, 0.05e-6, 0.1e-6, 0.2e-6)
    latency_sweep_seconds: tuple[float, ...] = (0.0, 1e-6, 2e-6, 3e-6, 10e-6)

    def __post_init__(self) -> None:
        if not np.isfinite([self.field_min_tesla, self.field_max_tesla]).all():
            raise ValueError("Field bounds must be finite, in tesla")
        if not 0 <= self.field_min_tesla < self.field_max_tesla:
            raise ValueError("Require 0 <= field_min_tesla < field_max_tesla")
        for key in (
            "sensing_times_seconds",
            "analysis_phases_radians",
            "phase_sweep_radians",
            "target_sweep_tesla",
            "latency_sweep_seconds",
        ):
            values = getattr(self, key)
            if not values or not np.isfinite(values).all():
                raise ValueError(f"{key} must contain finite SI values")
        if min(self.sensing_times_seconds) <= 0 or min(self.latency_sweep_seconds) < 0:
            raise ValueError("Sensing times must be positive and latencies nonnegative")
        for key in (
            "seed",
            "shots_per_setting",
            "train_samples",
            "test_samples",
            "calibration_samples",
        ):
            value = getattr(self, key)
            if type(value) is not int or value < (0 if key == "seed" else 2):
                raise ValueError(f"{key} must be an integer >= {0 if key == 'seed' else 2}")
        if self.time_distribution not in {"uniform", "choice"} or self.phase_distribution not in {
            "uniform",
            "choice",
        }:
            raise ValueError("Challenge distributions must be uniform or choice")
        if self.challenge_granularity not in {"setting", "shot"}:
            raise ValueError("challenge_granularity must be setting or shot")
        if not np.isfinite(self.actuation_window_seconds) or self.actuation_window_seconds < 0:
            raise ValueError("actuation_window_seconds must be finite and nonnegative")
        if not np.isfinite(self.target_tolerance_tesla) or self.target_tolerance_tesla <= 0:
            raise ValueError("target_tolerance_tesla must be finite and positive")
        for key in ("random_times", "random_phases"):
            if type(getattr(self, key)) is not bool:
                raise ValueError(f"{key} must be boolean")


def _attack(data: dict) -> AttackSpec:
    data = dict(data)
    data["components"] = tuple(_attack(c) for c in data.get("components", ()))
    return AttackSpec(**data)


def load_config(path: str | Path) -> ExperimentConfig:
    """Load YAML, rejecting unknown keys (including ambiguous Hz or time units)."""
    with Path(path).open() as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a YAML mapping")
    try:
        data["sensor"] = SensorConfig(**data.get("sensor", {}))
        data["attack"] = _attack(data.get("attack", {}))
        return ExperimentConfig(**data)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid configuration {path}: {exc}") from exc
