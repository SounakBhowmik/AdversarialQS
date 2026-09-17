"""Seeded challenges with disjoint estimation and verification acquisitions."""

from dataclasses import dataclass

import numpy as np

from ..config import ExperimentConfig
from ..control.commands import ControlCommand


@dataclass(frozen=True)
class Challenge:
    """Trusted scheduler record; nominal time is a public prior, not a disclosure."""

    command: ControlCommand
    nominal_time_seconds: float
    subset: str
    shots: int
    randomized: bool
    actuation_window_seconds: float


def generate(
    config: ExperimentConfig, rng: np.random.Generator, sequence_id: str
) -> list[Challenge]:
    """Generate two independently sampled subsets; shot mode uses one shot per ID."""
    result = []
    repetitions = config.shots_per_setting if config.challenge_granularity == "shot" else 1
    for subset in ("estimation", "verification"):
        for nominal in config.sensing_times_seconds:
            for alpha in config.analysis_phases_radians:
                for _ in range(repetitions):
                    t = nominal
                    phase = alpha
                    if config.random_times:
                        t = float(
                            rng.choice(config.sensing_times_seconds)
                            if config.time_distribution == "choice"
                            else rng.uniform(
                                min(config.sensing_times_seconds), max(config.sensing_times_seconds)
                            )
                        )
                    if config.random_phases:
                        phase = float(
                            rng.choice(config.analysis_phases_radians)
                            if config.phase_distribution == "choice"
                            else rng.uniform(0, 2 * np.pi)
                        )
                    result.append(
                        Challenge(
                            ControlCommand(t, phase, challenge_id=f"{sequence_id}:{len(result)}"),
                            nominal,
                            subset,
                            1 if repetitions > 1 else config.shots_per_setting,
                            config.random_times or config.random_phases,
                            config.actuation_window_seconds,
                        )
                    )
    return result
