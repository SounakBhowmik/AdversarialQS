"""Field recovery, state-kernel conventions and meaningful held-out detection."""

from dataclasses import replace

import numpy as np
import pytest

from adversarial_quantum_sensing.config import AttackSpec, ExperimentConfig, SensorConfig
from adversarial_quantum_sensing.control.commands import ControlCommand
from adversarial_quantum_sensing.defense.challenge import generate
from adversarial_quantum_sensing.defense.verifier import verify
from adversarial_quantum_sensing.estimators.maximum_likelihood import MaximumLikelihood
from adversarial_quantum_sensing.estimators.quantum_kernel import check_gram, state_kernel
from adversarial_quantum_sensing.experiments.runner import acquire
from adversarial_quantum_sensing.measurement.sampling import Observation
from adversarial_quantum_sensing.metrics import bernoulli_kl, uhlmann_fidelity
from adversarial_quantum_sensing.physics.density_matrix import simulate
from adversarial_quantum_sensing.physics.ramsey import probability_zero


def test_mle_recovers_field_and_time_dependent_phase_bias() -> None:
    """Single-time quadrature measurements isolate the delta_B=-delta_phi/(gamma*t) law."""
    from adversarial_quantum_sensing.constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA

    sensor = SensorConfig()
    b, delta = 0.7e-6, 0.05
    mle = MaximumLikelihood(sensor, (0.5e-6, 0.9e-6))
    for t in (5e-6, 10e-6, 20e-6):
        obs = [
            Observation(
                ControlCommand(t, a),
                round(float(probability_zero(b, t, a + delta, sensor)) * 10**8),
                10**8,
                "estimation",
            )
            for a in (0, np.pi / 2)
        ]
        estimate = mle.predict(obs)
        # Deterministic count rounding is <1e-8 in probability; error tolerance is 1 pT.
        assert abs(estimate.field_tesla - (b - delta / (GAMMA * t))) < 1e-12
    assert set(vars(mle)) == {"sensor", "bounds"}
    assert "true_field_tesla" not in SensorConfig.__dataclass_fields__


def test_kernels_and_fidelity_convention() -> None:
    """HS is PSD; squared fidelity distinguishes root/squared/accidentally fourth-power."""
    zero = np.diag([1, 0]).astype(complex)
    plus = np.ones((2, 2), dtype=complex) / 2
    assert np.isclose(uhlmann_fidelity(zero, plus), 0.5)
    assert np.isclose(uhlmann_fidelity(np.eye(2) / 2, zero), 0.5)
    states = np.array(
        [
            [simulate(b, ControlCommand(t), SensorConfig()).preanalysis for t in (5e-6, 20e-6)]
            for b in np.linspace(0, 2e-6, 25)
        ]
    )
    for kind in ("hilbert_schmidt", "squared_fidelity"):
        gram = state_kernel(states, states, kind)
        assert check_gram(gram)["psd_within_1e-10"]
        np.testing.assert_allclose(gram, gram.T, atol=1e-14)
    with pytest.raises(ValueError):
        check_gram(np.array([[1, 2], [0, 1]]))
    assert np.isinf(bernoulli_kl(np.array([1.0]), np.array([0.0])))[0]


def test_random_time_breaks_precommitment_but_not_immediate_spoof() -> None:
    """Same target under high shot count: inconsistent nominal-time spoof is detected."""
    cfg = ExperimentConfig(random_times=True, shots_per_setting=100_000)
    challenges = generate(cfg, np.random.default_rng(8), "test")
    mle = MaximumLikelihood(cfg.sensor, (cfg.field_min_tesla, cfg.field_max_tesla))
    scores = {}
    for profile in ("A1", "A3"):
        a = acquire(
            0.8e-6,
            challenges,
            AttackSpec(kind="spoof", profile=profile, target_displacement_tesla=0.15e-6),
            cfg.sensor,
            np.random.default_rng(20),
            np.random.default_rng(21),
            False,
        )
        scores[profile] = verify(a.observations, mle)
    assert scores["A1"]["standardized_residual"] > 100
    assert scores["A3"]["standardized_residual"] < 10
    assert abs(scores["A3"]["field_tesla"] - 0.95e-6) < 2e-9
    # Reusing even one challenge identifier across the split must fail.
    first = a.observations[0]
    bad = [first, replace(first, subset="verification")]
    with pytest.raises(ValueError, match="overlap"):
        verify(bad, mle)
