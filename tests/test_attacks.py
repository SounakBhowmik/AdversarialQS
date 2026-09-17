"""Attack placement, spoof identifiability and capability boundaries."""

import numpy as np
import pytest

from adversarial_quantum_sensing.attacks.base import attacker_view, execute, perturbation
from adversarial_quantum_sensing.config import AttackSpec, ExperimentConfig, SensorConfig
from adversarial_quantum_sensing.constants import GAMMA_RAD_PER_SECOND_TESLA as GAMMA
from adversarial_quantum_sensing.control.commands import ControlCommand
from adversarial_quantum_sensing.defense.challenge import Challenge
from adversarial_quantum_sensing.experiments.runner import identifiability_control
from adversarial_quantum_sensing.physics.density_matrix import simulate


def challenge() -> Challenge:
    """Known actual/nominal mismatch makes accidental schedule leakage visible."""
    return Challenge(ControlCommand(37e-6, 0.6), 20e-6, "estimation", 1000, True, 2e-6)


def test_zero_and_analysis_boundary() -> None:
    """An analysis attack changes only the last stored state and the measurement."""
    q = challenge()
    sensor = SensorConfig()
    clean = simulate(0.7e-6, q.command, sensor)
    zero, _ = execute(AttackSpec(kind="phase", phase_radians=0), q)
    np.testing.assert_allclose(
        simulate(0.7e-6, zero, sensor).premeasurement, clean.premeasurement, atol=1e-15
    )
    attacked, _ = execute(AttackSpec(kind="phase", phase_radians=0.1), q)
    trace = simulate(0.7e-6, attacked, sensor)
    np.testing.assert_array_equal(trace.preanalysis, clean.preanalysis)
    assert np.linalg.norm(trace.premeasurement - clean.premeasurement) > 0.01


def test_preparation_attack_is_coherent() -> None:
    """Deterministic preparation I/Q distortion rotates a pure state without mixing."""
    q = challenge()
    sensor = SensorConfig(t2_star_seconds=1e20)
    command, _ = execute(
        AttackSpec(
            kind="iq",
            pulse="preparation",
            phase_radians=0.3,
            i_gain=1.2,
            q_gain=0.8,
            angle_scale=1.1,
        ),
        q,
    )
    trace = simulate(1e-6, command, sensor)
    clean = simulate(1e-6, q.command, sensor)
    assert np.linalg.norm(trace.preanalysis - clean.preanalysis) > 0.1
    assert abs(np.trace(trace.preanalysis @ trace.preanalysis) - 1) < 1e-14


def test_pulse_local_detuning_does_not_become_a_reference_attack() -> None:
    """An analysis-only frequency error cannot act backward on free precession."""
    q = challenge()
    sensor = SensorConfig(t2_star_seconds=1e20)
    command, _ = execute(AttackSpec(kind="iq", pulse="analysis", detuning_rad_per_second=1e7), q)
    clean = simulate(0.7e-6, q.command, sensor)
    attacked = simulate(0.7e-6, command, sensor)
    np.testing.assert_array_equal(clean.preanalysis, attacked.preanalysis)
    assert np.linalg.norm(clean.premeasurement - attacked.premeasurement) > 0.01
    assert abs(np.trace(attacked.premeasurement @ attacked.premeasurement) - 1) < 1e-14


def test_global_delay_vs_separation_and_zero_field() -> None:
    """Only pulse separation accumulates extra static phase; timing cannot spoof B=0."""
    q = challenge()
    sensor = SensorConfig(t2_star_seconds=1e20)
    delayed, _ = execute(AttackSpec(kind="delay", absolute_seconds=1), q)
    timed, _ = execute(AttackSpec(kind="timing", relative_timing_error=0.1), q)
    clean = simulate(1e-6, q.command, sensor)
    np.testing.assert_array_equal(clean.preanalysis, simulate(1e-6, delayed, sensor).preanalysis)
    assert np.linalg.norm(clean.preanalysis - simulate(1e-6, timed, sensor).preanalysis) > 0.1
    np.testing.assert_allclose(
        simulate(0, timed, sensor).preanalysis,
        simulate(0, q.command, sensor).preanalysis,
        atol=1e-15,
    )
    with pytest.raises(ValueError, match="separation"):
        execute(AttackSpec(kind="timing", absolute_seconds=-1), q)


def test_exact_spoof_sign_and_identifiability() -> None:
    """Both pulse surfaces can mimic +delta_B; their raw phase signs differ."""
    assert identifiability_control(ExperimentConfig())["equivalent"]
    q = challenge()
    spec = AttackSpec(kind="spoof", profile="A3", target_displacement_tesla=0.1e-6)
    delta = perturbation(spec, attacker_view(spec, q))
    assert np.isclose(delta.phase_radians, -GAMMA * 0.1e-6 * q.command.sensing_duration_seconds)


@pytest.mark.parametrize(
    "profile,latency,expected",
    [("A0", 0, None), ("A1", 0, 20e-6), ("A2", 1e-6, 37e-6), ("A2", 3e-6, 20e-6), ("A3", 0, 37e-6)],
)
def test_attacker_information(profile: str, latency: float, expected: float | None) -> None:
    """Profiles expose neither true field nor hidden states or unrestricted configuration."""
    view = attacker_view(AttackSpec(profile=profile, latency_seconds=latency), challenge())
    assert view.sensing_duration_seconds == expected
    assert set(vars(view)) == {
        "profile",
        "challenge_id",
        "sensing_duration_seconds",
        "analysis_phase_radians",
        "commitment_time_seconds",
        "challenge_disclosure_time_seconds",
        "information",
    }
    if expected != 37e-6:
        assert view.analysis_phase_radians is None


def test_frequency_attack_follows_secret_time_without_disclosure() -> None:
    """An autonomous frequency offset remains field-equivalent despite time secrecy."""
    q = challenge()
    spec = AttackSpec(kind="frequency", profile="A0", target_displacement_tesla=0.15e-6)
    command, _ = execute(spec, q)
    np.testing.assert_allclose(
        simulate(0.7e-6, command, SensorConfig()).preanalysis,
        simulate(0.85e-6, q.command, SensorConfig()).preanalysis,
        atol=2e-15,
    )


def test_composite_applies_in_declared_order() -> None:
    """Phase then unbalanced Cartesian gain differs from gain then phase."""
    phase = AttackSpec(kind="phase", phase_radians=0.4)
    iq = AttackSpec(kind="iq", i_gain=1.4, q_gain=0.7)
    first, logs = execute(AttackSpec(kind="composite", components=(phase, iq)), challenge())
    second, _ = execute(AttackSpec(kind="composite", components=(iq, phase)), challenge())
    assert not np.isclose(first.analysis_phase_radians, second.analysis_phase_radians)
    assert logs[1]["original_command"] == logs[0]["attacked_command"]
