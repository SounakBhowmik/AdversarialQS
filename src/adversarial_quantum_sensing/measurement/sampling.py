"""Measurement-only estimator inputs and explicit random generators."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from ..control.commands import ControlCommand
from ..physics.density_matrix import paulis


@dataclass(frozen=True)
class Observation:
    """Protected intended challenge and zero count; contains no true field."""

    command: ControlCommand
    zeros: int
    shots: int
    subset: str

    def __post_init__(self) -> None:
        if self.shots < 1 or not 0 <= self.zeros <= self.shots:
            raise ValueError("Require 0 <= zeros <= shots and shots > 0")
        if self.subset not in {"estimation", "verification"}:
            raise ValueError("Unknown observation subset")


def sample_zeros(probability: float, shots: int, rng: np.random.Generator) -> int:
    """Draw a binomial zero count using an injected readout RNG."""
    if not np.isfinite(probability) or not 0 <= probability <= 1 or shots < 1:
        raise ValueError("Require a probability in [0,1] and positive shots")
    return int(rng.binomial(shots, probability))


def tomography(
    rho: NDArray, shots_per_axis: int, readout_error: float, rng: np.random.Generator
) -> NDArray:
    """Estimate XYZ on independent copies, correct known readout, project Bloch ball.

    This diagnostic assumes trusted tomography axes and costs 3*shots_per_axis
    extra preparations. It is not free information from the Ramsey Z counts.
    """
    if not 0 <= readout_error < 0.5:
        raise ValueError("readout_error must be in [0,0.5)")
    axes = paulis()
    expectations = np.einsum("aij,ji->a", axes, rho).real
    probabilities = np.clip((1 + (1 - 2 * readout_error) * expectations) / 2, 0, 1)
    counts = np.array([sample_zeros(p, shots_per_axis, rng) for p in probabilities])
    bloch = (2 * counts / shots_per_axis - 1) / (1 - 2 * readout_error)
    bloch /= max(1.0, float(np.linalg.norm(bloch)))
    return (np.eye(2) + np.einsum("a,aij->ij", bloch, axes)) / 2
