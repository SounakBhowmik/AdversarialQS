"""Headless research figures, each with caption and resolved-configuration references."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_results(runs: list[dict], output: Path) -> None:
    """Generate the ten comparison views from actual results, omitting absent sweeps."""
    figures = output / "figures"
    figures.mkdir()
    frame = pd.concat([r["results"] for r in runs], ignore_index=True)
    mle = frame[frame.estimator == "maximum_likelihood"]

    def save(name: str, xlabel: str, ylabel: str, caption: str) -> None:
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(alpha=0.2)
        plt.tight_layout()
        plt.savefig(figures / f"{name}.png", dpi=160)
        plt.close()
        (figures / f"{name}.json").write_text(
            json.dumps(
                {
                    "caption": caption,
                    "configuration_files": [f"../{r['name']}/resolved_config.yaml" for r in runs],
                    "source": "../results.csv",
                },
                indent=2,
            )
        )

    plt.figure(figsize=(7, 5))
    clean = frame[(frame.condition == "clean") & (frame.scenario == runs[0]["name"])]
    for label, group in clean.groupby("estimator"):
        plt.scatter(
            group.true_field_tesla * 1e6,
            group.estimated_field_tesla * 1e6,
            s=14,
            alpha=0.6,
            label=label,
        )
    limits = (frame.true_field_tesla.min() * 1e6, frame.true_field_tesla.max() * 1e6)
    plt.plot(limits, limits, "k--", linewidth=1)
    plt.legend(fontsize=7)
    save(
        "clean_estimates",
        "True field B (µT)",
        "Estimated field (µT)",
        "Clean held-out predictions; exact-state oracle is an information upper bound, "
        "not guaranteed best accuracy.",
    )

    phase = frame[
        (frame.condition == "attacked")
        & frame.scenario.str.startswith("phase_")
        & ~frame.scenario.eq("phase_only")
    ]
    if len(phase):
        plt.figure(figsize=(7, 5))
        for label, group in phase.groupby("estimator"):
            means = (
                group.assign(absolute_error=np.abs(group.error_tesla) * 1e9)
                .groupby("phase_radians")
                .absolute_error.mean()
            )
            plt.plot(means.index, means.values, "o-", label=label)
        plt.xscale("log")
        plt.legend(fontsize=7)
        save(
            "phase_error",
            "Analysis phase offset δφ (rad)",
            "Mean absolute field error (nT)",
            "Direct positive analysis phase offsets; finite-shot floor and phase aliases "
            "can mask small biases.",
        )

    target = frame[
        (frame.condition == "attacked")
        & frame.scenario.str.startswith("target_")
        & frame.target_in_bounds
    ]
    if len(target):
        plt.figure(figsize=(7, 5))
        for label, group in target.groupby("estimator"):
            means = group.groupby("target_displacement_tesla").target_success.mean()
            plt.plot(means.index * 1e9, means.values, "o-", label=label)
        plt.ylim(-0.03, 1.03)
        plt.legend(fontsize=7)
        save(
            "target_success",
            "Requested displacement ΔB (nT)",
            "Target success probability",
            "Targets outside estimator bounds excluded; "
            "tolerance is in each resolved configuration.",
        )

    plt.figure(figsize=(7, 5))
    for run in runs:
        roc = run["roc"]["standardized_residual"]
        plt.plot(roc["fpr"], roc["tpr"], label=run["name"])
    plt.plot([0, 1], [0, 1], "k--", linewidth=1)
    plt.legend(fontsize=6, ncol=2)
    save(
        "detector_roc",
        "False positive rate",
        "True positive rate",
        "ROC on independent clean/attacked test sequences. "
        "Calibration data are excluded from ROC evaluation.",
    )

    plt.figure(figsize=(7, 5))
    for run in runs:
        success = run["summary"]["attacked/maximum_likelihood"]["target_success_rate_in_bounds"]
        plt.scatter(
            run["detector"]["standardized_residual"]["tpr_at_calibrated_5pct"],
            success,
            label=run["name"],
        )
    plt.legend(fontsize=6, ncol=2)
    save(
        "efficacy_detection",
        "Detection probability (clean-calibrated 5% threshold)",
        "Target success probability",
        "Joint efficacy/detection view. Target success is meaningful for spoof/reference "
        "scenarios; direct phase scenarios use the configured diagnostic target.",
    )

    schedule_names = [
        "fixed",
        "phase_only",
        "random_time",
        "random_time_phase",
        "immediate_A3",
        "reference_A0",
    ]
    schedule = [r for r in runs if r["name"] in schedule_names]
    if schedule:
        plt.figure(figsize=(8, 5))
        positions = np.arange(len(schedule))
        plt.bar(
            positions - 0.2,
            [
                r["summary"]["attacked/maximum_likelihood"]["target_success_rate_in_bounds"]
                for r in schedule
            ],
            width=0.4,
            label="Target success",
        )
        plt.bar(
            positions + 0.2,
            [r["detector"]["standardized_residual"]["tpr_at_calibrated_5pct"] for r in schedule],
            width=0.4,
            label="Detection",
        )
        plt.xticks(positions, [r["name"] for r in schedule], rotation=25, ha="right")
        plt.legend()
        save(
            "schedule_comparison",
            "Schedule and attacker capability",
            "Probability",
            "A1 nominal-time commitment unless labeled A3 or reference A0; "
            "empirical FPR is saved separately.",
        )

    latency = [r for r in runs if r["name"].startswith("latency_")]
    if latency:
        plt.figure(figsize=(7, 5))
        times = [r["config"]["attack"]["latency_seconds"] * 1e6 for r in latency]
        plt.plot(
            times,
            [
                r["summary"]["attacked/maximum_likelihood"]["target_success_rate_in_bounds"]
                for r in latency
            ],
            "o-",
            label="Target success",
        )
        plt.plot(
            times,
            [r["detector"]["standardized_residual"]["tpr_at_calibrated_5pct"] for r in latency],
            "o-",
            label="Detection",
        )
        plt.legend()
        save(
            "latency",
            "Challenge disclosure latency (µs)",
            "Probability",
            "A2 sees challenge iff latency <= configured actuation window. "
            "This is a deadline model, not measured hardware latency.",
        )

    attacked = mle[mle.condition == "attacked"]
    for filename, column, xlabel in (
        (
            "state_disturbance",
            "preanalysis_trace_distance",
            "Preanalysis trace distance (dimensionless)",
        ),
        (
            "kernel_distortion",
            "oracle_kernel_vector_l2",
            "Oracle HS kernel-vector L2 distortion (dimensionless)",
        ),
    ):
        plt.figure(figsize=(7, 5))
        for label, group in attacked.groupby("scenario"):
            plt.scatter(
                group[column], np.abs(group.error_tesla) * 1e9, s=10, alpha=0.6, label=label
            )
        plt.legend(fontsize=6, ncol=2)
        save(
            filename,
            xlabel,
            "Absolute MLE field error (nT)",
            "Diagnostics compare clean/attacked exact preanalysis states at identical true field "
            "and challenge. Analysis-only attacks should have zero preanalysis disturbance.",
        )

    if schedule:
        plt.figure(figsize=(8, 5))
        for label in frame.estimator.unique():
            plt.plot(
                [r["name"] for r in schedule],
                [r["summary"][f"clean/{label}"]["rmse_tesla"] * 1e9 for r in schedule],
                "o-",
                label=label,
            )
        plt.xticks(rotation=25, ha="right")
        plt.legend(fontsize=7)
        save(
            "clean_accuracy_cost",
            "Schedule and attacker capability",
            "Clean RMSE (nT)",
            "Equal Ramsey shot budgets; models retrained on each schedule distribution. "
            "Tomography additionally consumes three axis measurements per estimation setting.",
        )
