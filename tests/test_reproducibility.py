"""Configuration validation, RNG separation, learner execution and output contract."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from adversarial_quantum_sensing.config import AttackSpec, ExperimentConfig, load_config
from adversarial_quantum_sensing.defense.challenge import generate
from adversarial_quantum_sensing.experiments.output import write_run
from adversarial_quantum_sensing.experiments.runner import run_scenario
from adversarial_quantum_sensing.measurement.sampling import sample_zeros


def test_challenge_and_sampling_seeds() -> None:
    """Seeds reproduce random challenges and counts, while changed seeds alter both."""
    config = ExperimentConfig(random_times=True, random_phases=True)
    first = generate(config, np.random.default_rng(1), "first")
    assert first == generate(config, np.random.default_rng(1), "first")
    assert first != generate(config, np.random.default_rng(2), "first")
    counts = [np.random.default_rng(s).binomial(1000, 0.4, 100) for s in (1, 1, 2)]
    np.testing.assert_array_equal(counts[0], counts[1])
    assert not np.array_equal(counts[0], counts[2])
    assert sample_zeros(0.5, 1000, np.random.default_rng(4)) == sample_zeros(
        0.5, 1000, np.random.default_rng(4)
    )
    shot = generate(
        replace(config, challenge_granularity="shot", shots_per_setting=3),
        np.random.default_rng(3),
        "shot",
    )
    assert len(shot) == len(first) * 3
    assert all(q.shots == 1 for q in shot)
    assert len({q.command.challenge_id for q in shot}) == len(shot)


@pytest.mark.parametrize(
    "data",
    [
        "sensor: {readout_error: 0.7}",
        "sensor: {t2_star_seconds: -1}",
        "sensing_times_hz: [100]",
        "shots_per_setting: 2.5",
        "sensor: {t2_star_seconds: .nan}",
        "random_times: 'false'",
        "attack: {detuning_hz: 2}",
    ],
)
def test_invalid_config_rejected(tmp_path: Path, data: str) -> None:
    """Reject invalid probabilities, units, scalar types and nonfinite constants."""
    path = tmp_path / "bad.yaml"
    path.write_text(data)
    with pytest.raises(ValueError):
        load_config(path)


def test_supplied_configs_load() -> None:
    """Every documented starter configuration resolves successfully."""
    for path in Path("configs").glob("*.yaml"):
        assert isinstance(load_config(path), ExperimentConfig)


def test_end_to_end_reproducibility_and_all_estimators() -> None:
    """A small full experiment is deterministic, including learned predictions."""
    config = ExperimentConfig(train_samples=16, test_samples=4, calibration_samples=8)
    first, second = run_scenario(config, "tiny"), run_scenario(config, "tiny")
    pd.testing.assert_frame_equal(first["results"], second["results"])
    assert len(first["results"].estimator.unique()) == 6
    assert np.isfinite(first["results"].estimated_field_tesla).all()
    np.testing.assert_array_equal(first["states_clean"], second["states_clean"])
    changed_attack = run_scenario(
        replace(config, attack=AttackSpec(kind="phase", phase_radians=0.1)), "tiny"
    )
    # Attacked binomial rejection sampling must not change later clean noise.
    pd.testing.assert_frame_equal(
        first["results"].query("condition == 'clean'")[["estimated_field_tesla", "nll"]],
        changed_attack["results"].query("condition == 'clean'")[["estimated_field_tesla", "nll"]],
    )


def test_artifacts_and_overwrite_protection(tmp_path: Path) -> None:
    """Completed runs include manifest, counts, states, config and figure metadata."""
    import json

    output = tmp_path / "run"
    config = ExperimentConfig(train_samples=8, test_samples=3, calibration_samples=4)
    write_run([("tiny", config)], output)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert "config.py" in manifest["source_sha256"]
    assert (output / "tiny" / "audit.jsonl").is_file()
    assert (output / "tiny" / "states.npz").is_file()
    assert (output / "figures" / "clean_estimates.json").is_file()
    with pytest.raises(FileExistsError):
        write_run([("tiny", config)], output)
