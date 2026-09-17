"""Physical invariants and independent analytical/density-matrix agreement."""

from dataclasses import replace

import numpy as np
import pytest

from adversarial_quantum_sensing.config import SensorConfig
from adversarial_quantum_sensing.control.commands import ControlCommand
from adversarial_quantum_sensing.measurement.sampling import tomography
from adversarial_quantum_sensing.metrics import uhlmann_fidelity
from adversarial_quantum_sensing.physics.density_matrix import simulate
from adversarial_quantum_sensing.physics.pulse_model import simulate_pulses
from adversarial_quantum_sensing.physics.ramsey import probability_zero


def test_density_and_analytical_agreement() -> None:
    """Independent matrix rotations reproduce the closed expression across many phases."""
    rng = np.random.default_rng(4)
    sensor = SensorConfig(dephasing_exponent=1.5)
    for _ in range(100):
        b, t, alpha = rng.uniform(0, 2e-6), rng.uniform(0, 150e-6), rng.uniform(-10, 10)
        state = simulate(b, ControlCommand(t, alpha), sensor)
        # A handful of 2x2 products should agree within ~10 floating-point ulps.
        assert abs(state.probability_zero - probability_zero(b, t, alpha, sensor)) < 2e-15
        for rho in (state.initialized, state.prepared, state.preanalysis, state.premeasurement):
            np.testing.assert_allclose(rho, rho.conj().T, atol=1e-14)
            assert abs(np.trace(rho) - 1) < 1e-14
            assert np.linalg.eigvalsh(rho).min() > -1e-14
        assert 0 <= state.probability_zero <= 1


def test_dephasing_and_readout_have_distinct_boundaries() -> None:
    """Dephasing damps transverse coherence; readout changes counts, not density state."""
    c = ControlCommand(100e-6)
    pure_readout = simulate(0, c, SensorConfig(readout_error=0))
    noisy_readout = simulate(0, c, SensorConfig(readout_error=0.2))
    assert np.isclose(pure_readout.preanalysis[0, 1], np.exp(-1) / 2)
    np.testing.assert_array_equal(pure_readout.premeasurement, noisy_readout.premeasurement)
    assert noisy_readout.probability_zero < pure_readout.probability_zero


def test_tomography_is_physical_and_converges() -> None:
    """Shot tomography recovers a known mixed state with physical Bloch projection."""
    rho = simulate(0.8e-6, ControlCommand(20e-6), SensorConfig()).preanalysis
    estimate = tomography(rho, 100_000, 0.1, np.random.default_rng(22))
    assert np.linalg.eigvalsh(estimate).min() >= -1e-14
    assert uhlmann_fidelity(rho, estimate) > 0.999


def test_optional_pulse_limit() -> None:
    """Rectangular pulses approach the instantaneous model as duration tends to zero."""
    pytest.importorskip("qutip")
    command = replace(ControlCommand(20e-6, 0.3), microwave_detuning_rad_per_second=1e4)
    sensor = SensorConfig()
    short = simulate_pulses(1e-6, command, sensor, 1e-12)
    ideal = simulate(1e-6, command, sensor)
    # Detuning * pulse length < 2e-7 rad, so a 1e-6 probability tolerance is conservative.
    assert abs(short.probability_zero - ideal.probability_zero) < 1e-6
