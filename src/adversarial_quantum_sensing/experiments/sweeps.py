"""Explicit experiment grids; every scenario uses a resolved immutable configuration."""

from dataclasses import replace

from ..config import AttackSpec, ExperimentConfig


def attack_scenarios(
    config: ExperimentConfig, suite: str = "phase"
) -> list[tuple[str, ExperimentConfig]]:
    """Build direct phase, target displacement, timing, I/Q, reference and composite sweeps."""
    scenarios = []
    if suite in {"phase", "all"}:
        scenarios += [
            (
                f"phase_{i}",
                replace(config, attack=replace(config.attack, kind="phase", phase_radians=p)),
            )
            for i, p in enumerate(config.phase_sweep_radians)
        ]
    if suite in {"target", "all"}:
        scenarios += [
            (
                f"target_{i}",
                replace(
                    config, attack=replace(config.attack, kind="spoof", target_displacement_tesla=d)
                ),
            )
            for i, d in enumerate(config.target_sweep_tesla)
        ]
    if suite in {"timing", "all"}:
        scenarios += [
            (
                f"timing_{i}",
                replace(config, attack=AttackSpec(kind="timing", relative_timing_error=r)),
            )
            for i, r in enumerate((0.001, 0.01, 0.05, 0.1))
        ]
    if suite in {"iq", "all"}:
        scenarios += [
            (
                f"iq_{pulse}",
                replace(
                    config,
                    attack=AttackSpec(
                        kind="iq",
                        pulse=pulse,
                        phase_radians=0.05,
                        angle_scale=1.05,
                        i_gain=1.05,
                        q_gain=0.95,
                    ),
                ),
            )
            for pulse in ("preparation", "analysis")
        ]
    if suite in {"frequency", "all"}:
        scenarios += [
            (
                "frequency",
                replace(
                    config,
                    attack=AttackSpec(
                        kind="frequency", profile="A0", target_displacement_tesla=0.1e-6
                    ),
                ),
            )
        ]
    if suite in {"composite", "all"}:
        components = (
            AttackSpec(kind="phase", phase_radians=0.03),
            AttackSpec(kind="timing", relative_timing_error=0.01),
        )
        scenarios += [
            (
                "composite",
                replace(config, attack=AttackSpec(kind="composite", components=components)),
            )
        ]
    if not scenarios:
        raise ValueError(f"Unknown attack suite: {suite}")
    return scenarios


def defense_scenarios(config: ExperimentConfig) -> list[tuple[str, ExperimentConfig]]:
    """Ablate time/phase secrecy, immediate access, delayed access and reference attacks."""
    scenarios = []
    for label, times, phases in (
        ("fixed", False, False),
        ("phase_only", False, True),
        ("random_time", True, False),
        ("random_time_phase", True, True),
    ):
        scenarios.append(
            (
                label,
                replace(
                    config,
                    random_times=times,
                    random_phases=phases,
                    attack=replace(config.attack, kind="spoof", profile="A1"),
                ),
            )
        )
    for i, latency in enumerate(config.latency_sweep_seconds):
        scenarios.append(
            (
                f"latency_{i}",
                replace(
                    config,
                    random_times=True,
                    attack=replace(
                        config.attack, kind="spoof", profile="A2", latency_seconds=latency
                    ),
                ),
            )
        )
    scenarios.append(
        (
            "immediate_A3",
            replace(
                config, random_times=True, attack=replace(config.attack, kind="spoof", profile="A3")
            ),
        )
    )
    scenarios.append(
        (
            "reference_A0",
            replace(
                config,
                random_times=True,
                attack=replace(config.attack, kind="frequency", profile="A0"),
            ),
        )
    )
    return scenarios


def sensitivity_scenarios(config: ExperimentConfig) -> list[tuple[str, ExperimentConfig]]:
    """Vary shot count, readout noise and dephasing with other parameters fixed."""
    return (
        [(f"shots_{n}", replace(config, shots_per_setting=n)) for n in (100, 1000, 5000)]
        + [
            (f"readout_{i}", replace(config, sensor=replace(config.sensor, readout_error=eta)))
            for i, eta in enumerate((0.0, 0.1, 0.2))
        ]
        + [
            (f"t2_{i}", replace(config, sensor=replace(config.sensor, t2_star_seconds=t)))
            for i, t in enumerate((50e-6, 100e-6, 200e-6))
        ]
    )
