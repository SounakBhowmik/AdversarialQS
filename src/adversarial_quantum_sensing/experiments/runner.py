"""Single-node acquisitions, clean training, independent calibration and held-out tests."""

import logging
import warnings
from dataclasses import asdict, dataclass, replace
from time import perf_counter

import numpy as np
import pandas as pd

from ..attacks.base import execute
from ..config import AttackSpec, ExperimentConfig, SensorConfig
from ..defense.challenge import Challenge, generate
from ..defense.verifier import verify
from ..estimators.classical import features, learning_estimators
from ..estimators.maximum_likelihood import MaximumLikelihood
from ..estimators.quantum_kernel import StateKernelRegressor, check_gram, state_kernel
from ..measurement.sampling import Observation, sample_zeros, tomography
from ..metrics import (
    bernoulli_kl,
    detection_metrics,
    log_likelihood_ratio,
    regression_metrics,
    trace_distance,
    uhlmann_fidelity,
)
from ..physics.density_matrix import simulate


@dataclass
class Acquisition:
    """Simulator-owned observations and privileged diagnostics kept in separate fields."""

    observations: list[Observation]
    states: np.ndarray
    tomography_states: np.ndarray
    probabilities: np.ndarray
    audit: list[dict]


def acquire(
    field_tesla: float,
    challenges: list[Challenge],
    attack: AttackSpec,
    sensor: SensorConfig,
    measurement_rng: np.random.Generator,
    tomography_rng: np.random.Generator,
    collect_tomography: bool = True,
) -> Acquisition:
    """Execute intended/attacked controls; return observations separately from exact states."""
    observations, states, reconstructed, probabilities, audit = [], [], [], [], []
    for challenge in challenges:
        attacked, records = execute(attack, challenge)
        trace = simulate(field_tesla, attacked, sensor)
        zeros = sample_zeros(trace.probability_zero, challenge.shots, measurement_rng)
        observations.append(
            Observation(challenge.command, zeros, challenge.shots, challenge.subset)
        )
        states.append([trace.initialized, trace.prepared, trace.preanalysis, trace.premeasurement])
        probabilities.append(trace.probability_zero)
        if challenge.subset == "estimation" and collect_tomography:
            reconstructed.append(
                tomography(trace.preanalysis, challenge.shots, sensor.readout_error, tomography_rng)
            )
        audit.append(
            {
                "challenge_id": challenge.command.challenge_id,
                "node_id": challenge.command.node_id,
                "subset": challenge.subset,
                "shots": challenge.shots,
                "zeros": zeros,
                "probability_zero": trace.probability_zero,
                "intended_command": asdict(challenge.command),
                "attacks": records,
                "physical_operation": asdict(trace.physical),
            }
        )
    return Acquisition(
        observations, np.array(states), np.array(reconstructed), np.array(probabilities), audit
    )


def _estimation(acquisition: Acquisition) -> list[Observation]:
    return [o for o in acquisition.observations if o.subset == "estimation"]


def _oracle(acquisition: Acquisition) -> np.ndarray:
    return acquisition.states[[o.subset == "estimation" for o in acquisition.observations], 2]


def run_scenario(config: ExperimentConfig, name: str) -> dict:
    """Train six estimators, calibrate two detectors, then evaluate clean/attacked pairs.

    Labels enter only supervised fit and the evaluator. MLE and verifier receive
    public sensor calibration and intended challenges, never ExperimentConfig.
    """
    started = perf_counter()
    seed_sequences = np.random.SeedSequence(config.seed).spawn(9)
    rngs = [np.random.default_rng(s) for s in seed_sequences]
    (
        train_field,
        train_challenge,
        train_readout,
        train_tomo,
        calibration_rng,
        test_field,
        test_challenge,
        test_readout,
        test_tomo,
    ) = rngs
    # Binomial samplers consume a probability-dependent number of random draws.
    # Separate conditions so an attack cannot alter later clean sample noise.
    test_readout = {
        label: np.random.default_rng(child)
        for label, child in zip(("clean", "attacked"), seed_sequences[7].spawn(2))
    }
    test_tomo = {
        label: np.random.default_rng(child)
        for label, child in zip(("clean", "attacked"), seed_sequences[8].spawn(2))
    }
    bounds = (config.field_min_tesla, config.field_max_tesla)
    mle = MaximumLikelihood(config.sensor, bounds)
    clean_spec = AttackSpec(kind="none")
    fields = train_field.uniform(*bounds, config.train_samples)
    training = [
        acquire(
            b,
            generate(config, train_challenge, f"{name}:train:{i}"),
            clean_spec,
            config.sensor,
            train_readout,
            train_tomo,
        )
        for i, b in enumerate(fields)
    ]
    x = np.array([features(_estimation(a)) for a in training])
    oracle_train = np.array([_oracle(a) for a in training])
    tomography_train = np.array([a.tomography_states for a in training])
    learners = learning_estimators(config.seed)
    training_diagnostics = {}
    for label, model in learners.items():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model.fit(x, fields * 1e6)
        iterations = getattr(model[-1], "n_iter_", None)
        training_diagnostics[label] = {
            "warnings": [str(w.message) for w in caught],
            "iterations": int(iterations) if iterations is not None else None,
        }
        if caught:
            logging.warning(
                "%s/%s: training warning saved in training_diagnostics.json", name, label
            )
    state_learners = {
        "tomography_krr": StateKernelRegressor().fit(tomography_train, fields * 1e6),
        "oracle_upper_bound": StateKernelRegressor(oracle=True).fit(oracle_train, fields * 1e6),
    }
    # Calibration has independent streams for field, challenge and measurement draws.
    calibration_streams = [
        np.random.default_rng(s)
        for s in np.random.SeedSequence(int(calibration_rng.integers(2**32))).spawn(4)
    ]
    cf, cq, cm, ct = calibration_streams
    calibration = []
    for i in range(config.calibration_samples):
        a = acquire(
            float(cf.uniform(*bounds)),
            generate(config, cq, f"{name}:calibration:{i}"),
            clean_spec,
            config.sensor,
            cm,
            ct,
            False,
        )
        calibration.append(verify(a.observations, mle))

    rows, logs, states_clean, states_attacked = [], [], [], []
    scores = {"clean": [], "attacked": []}
    for i, b in enumerate(test_field.uniform(*bounds, config.test_samples)):
        challenges = generate(config, test_challenge, f"{name}:test:{i}")
        clean = acquire(
            b, challenges, clean_spec, config.sensor, test_readout["clean"], test_tomo["clean"]
        )
        attacked = acquire(
            b,
            challenges,
            config.attack,
            config.sensor,
            test_readout["attacked"],
            test_tomo["attacked"],
        )
        states_clean.append(clean.states)
        states_attacked.append(attacked.states)
        logs.append(
            {
                "sample_id": i,
                "true_field_tesla": float(b),
                "clean": clean.audit,
                "attacked": attacked.audit,
            }
        )
        clean_vector = state_kernel(_oracle(clean)[None], oracle_train)[0]
        attack_vector = state_kernel(_oracle(attacked)[None], oracle_train)[0]
        diagnostics = {
            "preanalysis_fidelity": float(
                np.mean(
                    [
                        uhlmann_fidelity(a, z)
                        for a, z in zip(clean.states[:, 2], attacked.states[:, 2])
                    ]
                )
            ),
            "preanalysis_trace_distance": float(
                np.mean(
                    [
                        trace_distance(a, z)
                        for a, z in zip(clean.states[:, 2], attacked.states[:, 2])
                    ]
                )
            ),
            "premeasurement_trace_distance": float(
                np.mean(
                    [
                        trace_distance(a, z)
                        for a, z in zip(clean.states[:, 3], attacked.states[:, 3])
                    ]
                )
            ),
            "measurement_kl_nats_per_shot": float(
                np.mean(bernoulli_kl(attacked.probabilities, clean.probabilities))
            ),
            "oracle_kernel_vector_l2": float(np.linalg.norm(attack_vector - clean_vector)),
            "log_likelihood_ratio_attack_vs_clean": log_likelihood_ratio(
                np.array([o.zeros for o in attacked.observations]),
                np.array([o.shots for o in attacked.observations]),
                attacked.probabilities,
                clean.probabilities,
            ),
        }
        for condition, a in (("clean", clean), ("attacked", attacked)):
            score = verify(a.observations, mle)
            scores[condition].append(score)
            predictions = {"maximum_likelihood": score["field_tesla"]}
            predictions.update(
                {
                    label: float(model.predict(features(_estimation(a))[None])[0]) * 1e-6
                    for label, model in learners.items()
                }
            )
            predictions.update(
                {
                    "tomography_krr": float(
                        state_learners["tomography_krr"].predict(a.tomography_states[None])[0]
                    )
                    * 1e-6,
                    "oracle_upper_bound": float(
                        state_learners["oracle_upper_bound"].predict(_oracle(a)[None])[0]
                    )
                    * 1e-6,
                }
            )
            target = b + config.attack.target_displacement_tesla
            for label, predicted in predictions.items():
                rows.append(
                    {
                        "scenario": name,
                        "sample_id": i,
                        "condition": condition,
                        "estimator": label,
                        "true_field_tesla": b,
                        "estimated_field_tesla": predicted,
                        "error_tesla": predicted - b,
                        "phase_radians": config.attack.phase_radians,
                        "target_displacement_tesla": config.attack.target_displacement_tesla,
                        "target_in_bounds": bounds[0] <= target <= bounds[1],
                        "target_success": abs(predicted - target) <= config.target_tolerance_tesla,
                        "ci_covered": any(
                            lo <= b <= hi for lo, hi in score["confidence_intervals_tesla"]
                        )
                        if label == "maximum_likelihood"
                        else None,
                        "nll": score["nll"],
                        "standardized_residual": score["standardized_residual"],
                        "latency_seconds": config.attack.latency_seconds,
                        "profile": config.attack.profile,
                        "random_times": config.random_times,
                        "random_phases": config.random_phases,
                        **diagnostics,
                    }
                )
    frame = pd.DataFrame(rows)
    summary = {}
    for (condition, estimator), group in frame.groupby(["condition", "estimator"]):
        metrics = regression_metrics(
            group.true_field_tesla.to_numpy(), group.estimated_field_tesla.to_numpy()
        )
        eligible = group[group.target_in_bounds]
        metrics.update(
            {
                "target_success_rate_in_bounds": float(eligible.target_success.mean())
                if len(eligible)
                else None,
                "target_eligible_samples": len(eligible),
            }
        )
        if estimator == "maximum_likelihood":
            metrics["confidence_interval_coverage_95pct"] = float(group.ci_covered.mean())
        summary[f"{condition}/{estimator}"] = metrics
    detector, rocs = {}, {}
    for statistic in ("nll", "standardized_residual"):
        detector[statistic], rocs[statistic] = detection_metrics(
            np.array([s[statistic] for s in scores["clean"]]),
            np.array([s[statistic] for s in scores["attacked"]]),
            np.array([s[statistic] for s in calibration]),
        )
    all_clean, all_attacked = np.array(states_clean), np.array(states_attacked)
    gram_clean, gram_attack = (
        state_kernel(all_clean[:, :, 2], all_clean[:, :, 2]),
        state_kernel(all_attacked[:, :, 2], all_attacked[:, :, 2]),
    )
    return {
        "name": name,
        "training_diagnostics": training_diagnostics,
        "config": asdict(config),
        "results": frame,
        "summary": summary,
        "detector": detector,
        "roc": rocs,
        "calibration": calibration,
        "audit": logs,
        "states_clean": all_clean,
        "states_attacked": all_attacked,
        "kernel_diagnostics": {
            **{label: model.diagnostics for label, model in state_learners.items()},
            "clean_test_gram": check_gram(gram_clean),
            "attacked_test_gram": check_gram(gram_attack),
            "matrix_frobenius_distortion": float(np.linalg.norm(gram_attack - gram_clean)),
        },
        "seeds": [{"entropy": s.entropy, "spawn_key": s.spawn_key} for s in seed_sequences],
        "runtime_seconds": perf_counter() - started,
    }


def identifiability_control(config: ExperimentConfig) -> dict:
    """Compare exact analysis/preparation spoof distributions with clean B+delta_B."""
    rng = np.random.default_rng(config.seed)
    delta = config.attack.target_displacement_tesla
    maximum = {"analysis": 0.0, "preparation": 0.0}
    random_config = replace(
        config, random_times=True, random_phases=True, challenge_granularity="setting"
    )
    challenges = generate(random_config, rng, "identifiability")
    for b in np.linspace(config.field_min_tesla, config.field_max_tesla, 11):
        for q in challenges:
            shifted = simulate(b + delta, q.command, config.sensor)
            for pulse in maximum:
                attacked, _ = execute(
                    AttackSpec(
                        kind="spoof", profile="A3", pulse=pulse, target_displacement_tesla=delta
                    ),
                    q,
                )
                p = simulate(b, attacked, config.sensor).probability_zero
                maximum[pulse] = max(maximum[pulse], abs(p - shifted.probability_zero))
    return {
        "target_displacement_tesla": delta,
        "maximum_probability_difference": maximum,
        "tolerance": 1e-12,
        "equivalent": all(v < 1e-12 for v in maximum.values()),
        "interpretation": "Identical output distributions cannot be distinguished by any "
        "output-only detector. Positive analysis offsets instead mimic "
        "a negative field displacement.",
    }
